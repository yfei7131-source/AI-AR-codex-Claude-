import unittest
from app.core import Memory, to_hud
from app.provider import DemoProvider, ProviderError, OpenAIProvider
from unittest.mock import patch

class CoreTest(unittest.TestCase):
    def test_note_lifecycle(self):
        db=Memory(); row=db.note('  检查 FPC 连接  ')
        self.assertEqual(row['text'],'检查 FPC 连接')
        self.assertEqual(len(db.snapshot()['notes']),1)
        self.assertTrue(db.wipe()['cleared'])
        self.assertEqual(db.snapshot()['notes'],[])
    def test_task_cannot_execute_without_confirmation(self):
        db=Memory(); t=db.draft_task('记录设备故障')
        self.assertEqual(t['status'],'awaiting_confirmation')
        saved=db.confirm_task(t['id'])
        self.assertEqual(saved['status'],'confirmed_local_only')
        with self.assertRaises(ValueError): db.confirm_task(t['id'])
    def test_hud(self):
        hud=to_hud('translate','a'*72)
        self.assertEqual(hud['title'],'AR 翻译')
        self.assertEqual(len(hud['lines']),3)
    def test_mock_marked_as_simulation(self):
        result=DemoProvider().respond('这是什么', 'data:image/jpeg;base64,abc')
        self.assertIn('模拟演示',result)
    def test_require_key(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY':''}):
            with self.assertRaises(ProviderError): OpenAIProvider()

if __name__=='__main__': unittest.main()
