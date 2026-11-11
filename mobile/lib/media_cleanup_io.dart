import 'dart:io';

/// Only call for a path freshly returned by ImageSource.camera, never a gallery original.
Future<void> deleteCapturedCache(String path) async {
  final file = File(path);
  if (await file.exists()) await file.delete();
}
