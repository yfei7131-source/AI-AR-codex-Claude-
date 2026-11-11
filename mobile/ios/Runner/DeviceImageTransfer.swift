import CryptoKit
import CoreFoundation
import Flutter
import Foundation

struct MediaTransferError: Error { let code: String }

/// Bounded, ephemeral URLSession. No cache, cookies, redirects or disk writes.
private final class BoundedDeviceHTTP: NSObject, URLSessionDataDelegate {
  private struct Pending {
    let limit: Int
    var data = Data()
    var response: HTTPURLResponse?
    let completion: (Result<(HTTPURLResponse, Data), MediaTransferError>) -> Void
  }
  private var pending: [Int: Pending] = [:]
  private lazy var session: URLSession = {
    let config = URLSessionConfiguration.ephemeral
    config.urlCache = nil; config.httpCookieStorage = nil; config.urlCredentialStorage = nil
    config.httpShouldSetCookies = false
    config.requestCachePolicy = .reloadIgnoringLocalCacheData
    config.timeoutIntervalForRequest = 6; config.timeoutIntervalForResource = 8
    return URLSession(configuration:config, delegate:self, delegateQueue:.main)
  }()
  func request(_ value: URLRequest, limit: Int,
               completion: @escaping (Result<(HTTPURLResponse, Data), MediaTransferError>) -> Void) {
    let task = session.dataTask(with:value)
    pending[task.taskIdentifier] = Pending(limit:limit, completion:completion); task.resume()
  }
  private func fail(_ task: URLSessionTask, _ code: String) {
    let item = pending.removeValue(forKey:task.taskIdentifier)
    task.cancel(); item?.completion(.failure(MediaTransferError(code:code)))
  }
  func invalidate() {
    let items = Array(pending.values); pending.removeAll(); session.invalidateAndCancel()
    items.forEach { $0.completion(.failure(MediaTransferError(code:"CANCELLED"))) }
  }
  func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                  newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
    completionHandler(nil); fail(task, "DEVICE_REDIRECT_DENIED")
  }
  func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                  completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
    guard var item = pending[dataTask.taskIdentifier], let http = response as? HTTPURLResponse else {
      completionHandler(.cancel); fail(dataTask, "INVALID_DEVICE_RESPONSE"); return
    }
    if response.expectedContentLength > Int64(item.limit) {
      completionHandler(.cancel); fail(dataTask, "DEVICE_RESPONSE_TOO_LARGE"); return
    }
    item.response = http; pending[dataTask.taskIdentifier] = item; completionHandler(.allow)
  }
  func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
    guard var item = pending[dataTask.taskIdentifier] else { return }
    guard item.data.count + data.count <= item.limit else { fail(dataTask, "DEVICE_RESPONSE_TOO_LARGE"); return }
    item.data.append(data); pending[dataTask.taskIdentifier] = item
  }
  func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
    guard let item = pending.removeValue(forKey:task.taskIdentifier) else { return }
    if let error = error as NSError? {
      let code = error.code == NSURLErrorTimedOut ? "MEDIA_TIMEOUT" :
        (error.code == NSURLErrorCancelled ? "CANCELLED" : "DEVICE_NETWORK_OR_PERMISSION_ERROR")
      item.completion(.failure(MediaTransferError(code:code)))
    } else if let response = item.response {
      item.completion(.success((response,item.data)))
    } else { item.completion(.failure(MediaTransferError(code:"INVALID_DEVICE_RESPONSE"))) }
  }
}

/// Implements DEVICE_MEDIA_V1: a local AP bearer lease, status, bounded Range
/// requests, request association and SHA256. It never uploads to an AI service.
final class DeviceImageTransfer {
  private let base: URL, token: String, requestID: Int
  private let http = BoundedDeviceHTTP()
  private var done: ((Result<[String:Any],MediaTransferError>) -> Void)?
  private var ended = false, image = Data()
  private var expectedHash = "", length = 0, frameID: UInt32 = 0
  private var deadline = Date.distantPast
  private var statusPoll: DispatchWorkItem?, statusTimer: DispatchWorkItem?
  private var awaitingFrame = true
  init(base: String, token: String, requestID: Int) throws {
    guard let parts = URLComponents(string:base), parts.scheme == "http", parts.host == "192.168.4.1",
          parts.port == nil || parts.port == 80, parts.user == nil, parts.password == nil,
          parts.path.isEmpty || parts.path == "/", parts.query == nil, parts.fragment == nil,
          let url = parts.url, token.range(of:"^[0-9a-fA-F]{64}$", options:.regularExpression) != nil,
          (0...65535).contains(requestID) else { throw MediaTransferError(code:"INVALID_DEVICE_ENDPOINT") }
    self.base = url; self.token = token; self.requestID = requestID
  }
  private func request(_ path: String, method: String = "GET", range: String? = nil) -> URLRequest {
    var value = URLRequest(url:base.appendingPathComponent(path))
    value.httpMethod = method; value.setValue("Bearer " + token, forHTTPHeaderField:"Authorization")
    value.setValue("no-store", forHTTPHeaderField:"Cache-Control")
    if let range = range { value.setValue(range, forHTTPHeaderField:"Range") }
    return value
  }
  func start(_ completion: @escaping (Result<[String:Any],MediaTransferError>) -> Void) {
    guard done == nil, !ended else { completion(.failure(MediaTransferError(code:"MEDIA_ALREADY_STARTED"))); return }
    done = completion
    let timeout = DispatchWorkItem { [weak self] in
      guard let self = self, self.awaitingFrame, !self.ended else { return }
      self.finish(.failure(MediaTransferError(code:"NO_FRAME_TIMEOUT")))
    }
    statusTimer = timeout; DispatchQueue.main.asyncAfter(deadline:.now()+8, execute:timeout)
    pollStatus()
  }
  private func pollStatus() {
    guard !ended, awaitingFrame else { return }
    http.request(request("v1/media/status"), limit:4096) { [weak self] result in
      guard let self = self, !self.ended else { return }
      switch result {
      case .failure(let error): self.finish(.failure(error))
      case .success(let (response,data)): self.readStatus(response,data)
      }
    }
  }
  private func waitForFrame() {
    guard !ended, awaitingFrame else { return }
    statusPoll?.cancel()
    let next = DispatchWorkItem { [weak self] in self?.pollStatus() }
    statusPoll = next; DispatchQueue.main.asyncAfter(deadline:.now()+0.2, execute:next)
  }
  private func integer(_ value: Any?) -> Int? {
    guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
          number.doubleValue.isFinite, number.doubleValue == Double(number.int64Value) else { return nil }
    return number.intValue
  }
  private func readStatus(_ response: HTTPURLResponse, _ data: Data) {
    guard response.statusCode == 200 else {
      finish(.failure(MediaTransferError(code: response.statusCode == 401 ? "MEDIA_UNAUTHORIZED_OR_EXPIRED" : "MEDIA_STATUS_FAILED"))); return
    }
    guard let object = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
          integer(object["version"]) == 1, object["source"] as? String == "device" else {
      finish(.failure(MediaTransferError(code:"INVALID_MEDIA_STATUS"))); return
    }
    guard let captured = object["captured"] as? NSNumber, CFGetTypeID(captured) == CFBooleanGetTypeID() else {
      finish(.failure(MediaTransferError(code:"INVALID_MEDIA_STATUS"))); return
    }
    if !captured.boolValue {
      guard object["frame"] is NSNull else { finish(.failure(MediaTransferError(code:"INVALID_MEDIA_STATUS"))); return }
      waitForFrame(); return // Capture ATT ACK may precede the camera worker. Never re-trigger capture.
    }
    guard let frame = object["frame"] as? [String:Any], let actualRequest = integer(frame["request_id"]),
          (0...65535).contains(actualRequest) else {
      finish(.failure(MediaTransferError(code:"INVALID_MEDIA_STATUS"))); return
    }
    if actualRequest != requestID { waitForFrame(); return } // An older frame is not this capture.
    guard
          let id = integer(frame["frame_id"]), id > 0, UInt64(id) <= UInt64(UInt32.max),
          let count = integer(frame["length"]), (4...2097152).contains(count),
          let hash = frame["sha256"] as? String, hash.range(of:"^[0-9a-fA-F]{64}$", options:.regularExpression) != nil,
          frame["mime"] as? String == "image/jpeg", frame["captured"] as? Bool == true,
          let expiry = integer(frame["expires_in_ms"]), (1...15000).contains(expiry) else {
      finish(.failure(MediaTransferError(code:"FRAME_REQUEST_OR_METADATA_MISMATCH"))); return
    }
    awaitingFrame = false
    statusTimer?.cancel(); statusTimer = nil; statusPoll?.cancel(); statusPoll = nil
    frameID = UInt32(id); length = count; expectedHash = hash.lowercased()
    deadline = Date().addingTimeInterval(Double(expiry)/1000)
    image.reserveCapacity(length); nextChunk()
  }
  private func nextChunk() {
    guard !ended else { return }
    guard Date() < deadline else { finish(.failure(MediaTransferError(code:"MEDIA_TIMEOUT"))); return }
    if image.count == length { verifyAndRelease(); return }
    let start = image.count, end = min(start+16384,length)-1
    http.request(request("v1/media/frame/\(frameID)", range:"bytes=\(start)-\(end)"), limit:end-start+1) { [weak self] result in
      guard let self = self, !self.ended else { return }
      switch result {
      case .failure(let error): self.finish(.failure(error))
      case .success(let (response,data)):
        let range = response.value(forHTTPHeaderField:"Content-Range")
        let etag = response.value(forHTTPHeaderField:"ETag")?.trimmingCharacters(in:CharacterSet(charactersIn:"\""))
        guard response.statusCode == 206, range == "bytes \(start)-\(end)/\(self.length)",
              etag?.lowercased() == self.expectedHash, data.count == end-start+1 else {
          self.finish(.failure(MediaTransferError(code:"FRAME_RANGE_OR_ETAG_MISMATCH"))); return
        }
        self.image.append(data); self.nextChunk()
      }
    }
  }
  private func verifyAndRelease() {
    let digest = SHA256.hash(data:image).map { String(format:"%02x",$0) }.joined()
    guard digest == expectedHash, image.count >= 4, image[0] == 0xff, image[1] == 0xd8, image[2] == 0xff else {
      finish(.failure(MediaTransferError(code:"FRAME_HASH_OR_JPEG_MISMATCH"))); return
    }
    // A failed DELETE is reported explicitly, never described as a confirmed remote deletion.
    http.request(request("v1/media/frame/\(frameID)", method:"DELETE"), limit:4096) { [weak self] result in
      guard let self = self, !self.ended else { return }
      var released = false
      if case .success(let (response,_)) = result { released = (200...299).contains(response.statusCode) }
      let output: [String:Any] = ["bytes":FlutterStandardTypedData(bytes:self.image), "mime":"image/jpeg",
        "request_id":self.requestID, "frame_id":Int(self.frameID), "sha256":self.expectedHash,
        "sha256_verified":true, "release_confirmed":released]
      self.finish(.success(output))
    }
  }
  func cancel() { finish(.failure(MediaTransferError(code:"CANCELLED"))) }
  private func finish(_ result: Result<[String:Any],MediaTransferError>) {
    guard !ended else { return }
    ended = true; let completion = done; done = nil
    statusTimer?.cancel(); statusTimer = nil; statusPoll?.cancel(); statusPoll = nil
    image.removeAll(keepingCapacity:false); http.invalidate(); completion?(result)
  }
}
