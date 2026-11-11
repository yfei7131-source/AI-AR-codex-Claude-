import unittest
from tools.check_repository import forbidden_path, secret_like


class RepositoryGuardTest(unittest.TestCase):
    def test_media_keys_and_build_cache_blocked(self):
        for path in (".env", ".env.local", "mobile/build/app.apk", "artifacts/private/photo.png", "mobile/.dart_tool/package_config.json", "firmware/managed_components/source.c", "docs/evidence/private.jpg", "tests/fixtures/photo.png", "tools/acceptance/label.jpg", "server-key.pem", "private.key", "ca.cer", "server.crt"):
            self.assertIsNotNone(forbidden_path(path), path)
        for path in (".env.example", "mobile/pubspec.lock", "firmware/sdkconfig.defaults", "mobile/android/app/src/main/res/mipmap-hdpi/ic_launcher.png", "firmware/dependencies.lock"):
            self.assertIsNone(forbidden_path(path), path)

    def test_recognized_secrets_fail_without_real_credentials(self):
        self.assertTrue(secret_like("sk-proj-" + "A" * 40))
        self.assertTrue(secret_like("-----BEGIN " + "PRIVATE KEY-----"))
        self.assertFalse(secret_like("OPENAI_API_KEY=\n"))


if __name__ == "__main__":
    unittest.main()
