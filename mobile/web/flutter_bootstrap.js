{{flutter_js}}
{{flutter_build_config}}

// Keep engine and fallback font requests on the Windows gateway origin.
_flutter.loader.load({config:{
  canvasKitBaseUrl:new URL('canvaskit/',document.baseURI).toString(),
  fontFallbackBaseUrl:new URL('fonts/fallback/',document.baseURI).toString()
}});
