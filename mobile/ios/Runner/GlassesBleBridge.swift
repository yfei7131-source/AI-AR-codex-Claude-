import CoreBluetooth
import CoreFoundation
import Flutter
import Foundation
import UIKit

/// Foreground-only central. Encrypted GATT permissions are enforced by the
/// peripheral; iOS owns pairing dialogs. We never report a fabricated bond.
final class GlassesBleBridge: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate, FlutterStreamHandler {
  private let serviceID = CBUUID(string: "8f13a001-6c55-4b8e-9d51-2f76a4b10000")
  private let controlID = CBUUID(string: "8f13a002-6c55-4b8e-9d51-2f76a4b10000")
  private let statusID = CBUUID(string: "8f13a003-6c55-4b8e-9d51-2f76a4b10000")
  private let mediaControlID = CBUUID(string: "8f13a004-6c55-4b8e-9d51-2f76a4b10000")
  private let mediaInfoID = CBUUID(string: "8f13a005-6c55-4b8e-9d51-2f76a4b10000")
  private let methods: FlutterMethodChannel
  private let events: FlutterEventChannel
  private var eventSink: FlutterEventSink?
  private var central: CBCentralManager?
  private var discovered: [UUID: CBPeripheral] = [:]
  private var peripheral: CBPeripheral?
  private var control: CBCharacteristic?, status: CBCharacteristic?
  private var mediaControl: CBCharacteristic?, mediaInfo: CBCharacteristic?
  private var ready = false, requestedScan = false
  private var scanSeconds = 10
  private var scanTimer: DispatchWorkItem?, connectTimer: DispatchWorkItem?, writeTimer: DispatchWorkItem?, mediaTimer: DispatchWorkItem?
  private var connectReply: FlutterResult?, mediaReply: FlutterResult?
  private var mediaPoll: DispatchWorkItem?
  private var mediaGeneration: UInt64 = 0
  private var mediaReadGeneration: UInt64?
  private var mediaRequestID = 0
  private var mediaOperation: UInt8 = 0
  private var mediaDeadline: TimeInterval = 0
  private struct Write { let bytes: Data; let characteristic: CBCharacteristic; let reply: (FlutterError?) -> Void }
  private var activeWrite: Write?, writes: [Write] = []
  private var transfer: DeviceImageTransfer?
  private var backgroundObserver: NSObjectProtocol?

  init(messenger: FlutterBinaryMessenger) {
    methods = FlutterMethodChannel(name: "aiar/device", binaryMessenger: messenger)
    events = FlutterEventChannel(name: "aiar/device_events", binaryMessenger: messenger)
    super.init()
    methods.setMethodCallHandler { [weak self] call, reply in
      guard let self = self else { reply(FlutterError(code: "DISPOSED", message: "原生设备通道已释放", details: nil)); return }
      self.handle(call, reply)
    }
    events.setStreamHandler(self)
    backgroundObserver = NotificationCenter.default.addObserver(
      forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main
    ) { [weak self] _ in self?.shutdown("APP_BACKGROUND") }
  }
  deinit { if let observer = backgroundObserver { NotificationCenter.default.removeObserver(observer) } }
  func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
    eventSink = events; return nil
  }
  func onCancel(withArguments arguments: Any?) -> FlutterError? { eventSink = nil; return nil }
  private func emit(_ value: [String: Any]) { eventSink?(value) }
  private func failure(_ code: String) -> FlutterError {
    FlutterError(code: code, message: "设备操作未完成：\(code)", details: nil)
  }
  private func bytes(_ value: Any?) -> Data? {
    if let typed = value as? FlutterStandardTypedData { return typed.data }
    return value as? Data
  }
  private var authorization: String {
    switch CBManager.authorization {
    case .allowedAlways: return "allowed"
    case .denied: return "denied"
    case .restricted: return "restricted"
    case .notDetermined: return "not_determined"
    @unknown default: return "unknown"
    }
  }
  private var powerState: String {
    guard let manager = central else { return "not_initialized" }
    switch manager.state {
    case .poweredOn: return "powered_on"
    case .poweredOff: return "powered_off"
    case .unauthorized: return "unauthorized"
    case .unsupported: return "unsupported"
    case .resetting: return "resetting"
    case .unknown: return "unknown"
    @unknown default: return "unknown"
    }
  }
  private func handle(_ call: FlutterMethodCall, _ reply: @escaping FlutterResult) {
    if UIApplication.shared.applicationState == .background &&
        !["permissions","disconnect","stopScan","cancelFetch"].contains(call.method) {
      reply(failure("APP_BACKGROUND")); return
    }
    let args = call.arguments as? [String: Any] ?? [:]
    switch call.method {
    case "permissions":
      reply(["bluetoothAuthorization": authorization, "bluetoothState": powerState,
             "localNetwork": "not_queryable_use_request_result", "backgroundCapture": false])
    case "scan":
      guard args["consent"] as? Bool == true, let seconds = args["seconds"] as? Int, (1...30).contains(seconds) else {
        reply(failure("SCAN_CONSENT_REQUIRED")); return
      }
      if authorization == "denied" || authorization == "restricted" { reply(failure("BLUETOOTH_DENIED")); return }
      requestedScan = true; scanSeconds = seconds
      if central == nil { central = CBCentralManager(delegate: self, queue: .main) }
      if central?.state == .poweredOn { beginScan() }
      reply(["requested": true, "state": powerState])
    case "stopScan": stopScan(); reply(nil)
    case "connect":
      guard connectReply == nil, peripheral == nil, let text = args["id"] as? String,
            let id = UUID(uuidString: text), let selected = discovered[id], central?.state == .poweredOn else {
        reply(failure("SELECT_SCANNED_DEVICE_OR_DISCONNECT_FIRST")); return
      }
      stopScan(); ready = false; peripheral = selected; selected.delegate = self; connectReply = reply
      emit(["type":"connection", "state":"connecting", "id":id.uuidString])
      central?.connect(selected, options: nil)
      let timeout = DispatchWorkItem { [weak self] in self?.shutdown("CONNECT_TIMEOUT") }
      connectTimer = timeout; DispatchQueue.main.asyncAfter(deadline: .now()+20, execute: timeout)
    case "disconnect": shutdown("DISCONNECTED"); reply(nil)
    case "writeControl":
      guard let data = bytes(call.arguments), validControl(data), ready, let characteristic = control else {
        reply(failure("INVALID_CONTROL_OR_NOT_READY")); return
      }
      let safeRevoke = data[1] == 3 || (data[1] == 4 && data[4] == 0)
      if safeRevoke { cancelTransfer(); finishMedia(failure("CANCELLED")); clearQueuedWrites("CANCELLED") }
      enqueue(Write(bytes:data, characteristic:characteristic, reply:{ error in
        if let error = error { reply(error) } else { reply(["written":8]) }
      }))
    case "mediaSession":
      guard let data = bytes(call.arguments), validMediaControl(data), ready,
            let characteristic = mediaControl else {
        reply(failure("MEDIA_UNSUPPORTED_OR_BUSY")); return
      }
      if data[1] == 3 {
        cancelTransfer(); finishMedia(failure("CANCELLED"))
        clearQueuedWrites("CANCELLED")
      }
      guard mediaInfo != nil, mediaReply == nil else { reply(failure("MEDIA_UNSUPPORTED_OR_BUSY")); return }
      mediaGeneration &+= 1
      let generation = mediaGeneration
      mediaReply = reply; mediaOperation = data[1]
      mediaRequestID = Int(data[2]) | Int(data[3])<<8
      mediaDeadline = ProcessInfo.processInfo.systemUptime + 10
      let timeout = DispatchWorkItem { [weak self] in
        guard let self = self, self.mediaGeneration == generation, self.mediaReply != nil else { return }
        self.shutdown("MEDIA_INFO_TIMEOUT")
      }
      mediaTimer = timeout; DispatchQueue.main.asyncAfter(deadline:.now()+10, execute:timeout)
      enqueue(Write(bytes:data, characteristic:characteristic, reply:{ [weak self] error in
        guard let self = self, self.mediaGeneration == generation else { return }
        if let error = error { self.finishMedia(error); return }
        self.readMediaInfo(generation) // ATT ACK means queued, not session/AP ready.
      }))
    case "fetchFrame":
      guard ready, transfer == nil, args["consent"] as? Bool == true,
            let base = args["baseUrl"] as? String, let token = args["token"] as? String,
            let requestID = args["requestId"] as? Int, (0...65535).contains(requestID) else {
        reply(failure("MEDIA_CONSENT_REQUIRED_OR_BUSY")); return
      }
      do {
        let fetcher = try DeviceImageTransfer(base:base, token:token, requestID:requestID)
        transfer = fetcher
        fetcher.start { [weak self, weak fetcher] result in
          guard let self = self, self.transfer === fetcher else { return }
          self.transfer = nil
          switch result {
          case .success(let value): reply(value)
          case .failure(let error): reply(self.failure(error.code))
          }
        }
      } catch { reply(failure("INVALID_DEVICE_MEDIA_ENDPOINT")) }
    case "cancelFetch": cancelTransfer(); finishMedia(failure("CANCELLED")); reply(nil)
    default: reply(FlutterMethodNotImplemented)
    }
  }
  private func beginScan() {
    guard requestedScan, central?.state == .poweredOn,
          UIApplication.shared.applicationState != .background else { return }
    scanTimer?.cancel(); discovered.removeAll()
    central?.scanForPeripherals(withServices:[serviceID], options:[CBCentralManagerScanOptionAllowDuplicatesKey:false])
    emit(["type":"scan", "state":"scanning"])
    let stop = DispatchWorkItem { [weak self] in self?.stopScan() }
    scanTimer = stop; DispatchQueue.main.asyncAfter(deadline: .now()+Double(scanSeconds), execute:stop)
  }
  private func stopScan() {
    requestedScan = false; scanTimer?.cancel(); scanTimer = nil; central?.stopScan()
    emit(["type":"scan", "state":"stopped"])
  }
  private func validControl(_ data: Data) -> Bool {
    guard data.count == 8, data[0] == 1, (1...5).contains(data[1]) else { return false }
    let argument = UInt32(data[4]) | UInt32(data[5])<<8 | UInt32(data[6])<<16 | UInt32(data[7])<<24
    return data[1] == 4 ? argument <= 1 : argument == 0
  }
  private func validMediaControl(_ data: Data) -> Bool {
    guard data.count == 20, data[0] == 2, (1...3).contains(data[1]), data[8...19].allSatisfy({ $0 == 0 }) else { return false }
    guard data[2] != 0 || data[3] != 0 else { return false } // 0 is the initial unprocessed snapshot.
    let ttl = UInt32(data[4]) | UInt32(data[5])<<8 | UInt32(data[6])<<16 | UInt32(data[7])<<24
    return data[1] == 1 ? (1000...120000).contains(ttl) : ttl == 0
  }
  private func validStatus(_ data: Data) -> Bool {
    data.count == 20 && data[0] == 1 && (data[6] <= 100 || data[6] == 255)
  }
  private func enqueue(_ write: Write) {
    guard writes.count < 8 else { write.reply(failure("WRITE_QUEUE_FULL")); return }
    writes.append(write); drainWrites()
  }
  private func drainWrites() {
    guard activeWrite == nil, !writes.isEmpty, let device = peripheral, device.state == .connected else { return }
    let next = writes.removeFirst()
    guard device.maximumWriteValueLength(for:.withResponse) >= next.bytes.count else {
      next.reply(failure("CONTROL_EXCEEDS_MTU")); drainWrites(); return
    }
    activeWrite = next; device.writeValue(next.bytes, for:next.characteristic, type:.withResponse)
    let timeout = DispatchWorkItem { [weak self] in self?.shutdown("WRITE_TIMEOUT") }
    writeTimer = timeout; DispatchQueue.main.asyncAfter(deadline:.now()+8, execute:timeout)
  }
  private func clearQueuedWrites(_ code: String) {
    let pending = writes; writes.removeAll(); pending.forEach { $0.reply(failure(code)) }
  }
  private func cancelTransfer() { transfer?.cancel() }
  private func finishMedia(_ value: Any?) {
    mediaTimer?.cancel(); mediaTimer = nil; mediaPoll?.cancel(); mediaPoll = nil
    let reply = mediaReply; mediaReply = nil
    mediaGeneration &+= 1; mediaOperation = 0; mediaRequestID = 0
    // Preserve any in-flight read generation until its callback; never treat an
    // old Read Long completion as the new operation's response.
    reply?(value)
  }
  private func scheduleMediaPoll(_ generation: UInt64) {
    guard mediaReply != nil, mediaGeneration == generation else { return }
    mediaPoll?.cancel()
    let next = DispatchWorkItem { [weak self] in self?.readMediaInfo(generation) }
    mediaPoll = next; DispatchQueue.main.asyncAfter(deadline:.now()+0.2, execute:next)
  }
  private func readMediaInfo(_ generation: UInt64) {
    guard mediaReply != nil, mediaGeneration == generation else { return }
    if UIApplication.shared.applicationState == .background { shutdown("APP_BACKGROUND"); return }
    guard ProcessInfo.processInfo.systemUptime < mediaDeadline else { shutdown("MEDIA_INFO_TIMEOUT"); return }
    guard ready, let info = mediaInfo, let device = peripheral, device.state == .connected else {
      finishMedia(failure("BLE_DISCONNECTED")); return
    }
    if mediaReadGeneration != nil { scheduleMediaPoll(generation); return }
    mediaReadGeneration = generation; device.readValue(for:info)
  }
  private func shutdown(_ code: String) {
    stopScan(); connectTimer?.cancel(); connectTimer = nil; writeTimer?.cancel(); writeTimer = nil
    finishMedia(failure(code)); mediaReadGeneration = nil
    cancelTransfer()
    ready = false; let device = peripheral
    peripheral = nil; control = nil; status = nil; mediaControl = nil; mediaInfo = nil
    let connect = connectReply; connectReply = nil; connect?(failure(code))
    let write = activeWrite; activeWrite = nil; write?.reply(failure(code))
    clearQueuedWrites(code)
    if let device = device { device.delegate = nil; central?.cancelPeripheralConnection(device) }
    emit(["type":"connection", "state":"disconnected", "reason":code])
  }
  func centralManagerDidUpdateState(_ central: CBCentralManager) {
    emit(["type":"permission", "authorization":authorization, "state":powerState])
    if central.state == .poweredOn { beginScan() }
    else if central.state != .unknown { shutdown("BLUETOOTH_"+powerState.uppercased()) }
  }
  func centralManager(_ central: CBCentralManager, didDiscover device: CBPeripheral,
                      advertisementData: [String : Any], rssi RSSI: NSNumber) {
    discovered[device.identifier] = device
    emit(["type":"discovered", "id":device.identifier.uuidString,
          "name":device.name ?? "AIAR device", "rssi":RSSI.intValue])
  }
  func centralManager(_ central: CBCentralManager, didConnect device: CBPeripheral) {
    guard peripheral === device else { central.cancelPeripheralConnection(device); return }
    emit(["type":"connection", "state":"link_connected"]); device.discoverServices([serviceID])
  }
  func centralManager(_ central: CBCentralManager, didFailToConnect device: CBPeripheral, error: Error?) {
    if peripheral === device { shutdown("CONNECT_FAILED") }
  }
  func centralManager(_ central: CBCentralManager, didDisconnectPeripheral device: CBPeripheral, error: Error?) {
    if peripheral === device { shutdown("BLE_DISCONNECTED") }
  }
  func peripheral(_ device: CBPeripheral, didDiscoverServices error: Error?) {
    guard peripheral === device else { return }
    guard error == nil, let service = device.services?.first(where: { $0.uuid == serviceID }) else {
      shutdown("SERVICE_UNAVAILABLE"); return
    }
    device.discoverCharacteristics([controlID,statusID,mediaControlID,mediaInfoID], for:service)
  }
  func peripheral(_ device: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
    guard peripheral === device else { return }
    guard error == nil else { shutdown("GATT_DISCOVERY_FAILED"); return }
    for characteristic in service.characteristics ?? [] {
      if characteristic.uuid == controlID { control = characteristic }
      if characteristic.uuid == statusID { status = characteristic }
      if characteristic.uuid == mediaControlID { mediaControl = characteristic }
      if characteristic.uuid == mediaInfoID { mediaInfo = characteristic }
    }
    guard let command = control, command.properties.contains(.write), let state = status,
          state.properties.contains(.read), state.properties.contains(.notify) else { shutdown("CONTROL_STATUS_UNAVAILABLE"); return }
    device.setNotifyValue(true, for:state)
  }
  func peripheral(_ device: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
    guard peripheral === device, characteristic.uuid == statusID else { return }
    guard error == nil, characteristic.isNotifying else { shutdown("STATUS_SUBSCRIBE_OR_PAIRING_FAILED"); return }
    device.readValue(for:characteristic) // encrypted GATT read may trigger iOS pairing
  }
  func peripheral(_ device: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
    guard peripheral === device else { return }
    if characteristic.uuid == mediaInfoID {
      let readGeneration = mediaReadGeneration; mediaReadGeneration = nil
      guard mediaReply != nil else { return }
      guard readGeneration == mediaGeneration else { scheduleMediaPoll(mediaGeneration); return }
      guard error == nil, let data = characteristic.value, data.count <= 512,
            let value = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
            let version = value["version"] as? Int, version == 2,
            let processed = value["request_id"] as? NSNumber, CFGetTypeID(processed) != CFBooleanGetTypeID(),
            processed.doubleValue == Double(processed.intValue), (0...65535).contains(processed.intValue),
            let readyValue = value["ready"] as? NSNumber, CFGetTypeID(readyValue) == CFBooleanGetTypeID() else {
        finishMedia(failure("MEDIA_INFO_OR_PAIRING_FAILED")); return
      }
      guard processed.intValue == mediaRequestID else { scheduleMediaPoll(mediaGeneration); return }
      if mediaOperation == 3 {
        if !readyValue.boolValue && value["error"] as? String == "revoked" { finishMedia(value) }
        else { scheduleMediaPoll(mediaGeneration) }
        return
      }
      if readyValue.boolValue { finishMedia(value); return }
      guard let state = value["error"] as? String else { finishMedia(failure("INVALID_MEDIA_STATE")); return }
      if ["disabled","ble_required","pairing_required","wifi_start_failed"].contains(state) || (mediaOperation == 2 && state == "revoked") {
        finishMedia(failure("MEDIA_"+state.uppercased())); return
      }
      if ["pairing_window_open","revoked"].contains(state) { scheduleMediaPoll(mediaGeneration) }
      else { finishMedia(failure("INVALID_MEDIA_STATE")) }
      return // Only matching processed request IDs complete; credentials never enter logs/events.
    }
    guard characteristic.uuid == statusID else { return }
    guard error == nil, let data = characteristic.value, validStatus(data) else { shutdown("STATUS_OR_PAIRING_FAILED"); return }
    emit(["type":"status", "bytes":FlutterStandardTypedData(bytes:data)])
    if !ready {
      guard data[2] & 1 != 0 else { return }
      ready = true; connectTimer?.cancel(); connectTimer = nil
      let reply = connectReply; connectReply = nil
      emit(["type":"connection", "state":"ready"])
      reply?(["connected":true, "status":FlutterStandardTypedData(bytes:data)])
    }
  }
  func peripheral(_ device: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
    guard peripheral === device, let active = activeWrite, active.characteristic.uuid == characteristic.uuid else { return }
    writeTimer?.cancel(); writeTimer = nil; activeWrite = nil
    active.reply(error == nil ? nil : failure("GATT_WRITE_OR_PAIRING_FAILED")); drainWrites()
  }
}
