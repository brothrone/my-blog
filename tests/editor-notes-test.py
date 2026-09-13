"""Keep legacy notes and new review facts in the writing handoff."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blog-editor'))
import server

class NotesTest(unittest.TestCase):
    def test_review_and_legacy_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = server.NOTES
            self.addCleanup(setattr, server, 'NOTES', old)
            server.NOTES = Path(tmp)
            for info in ({'basic': '기존 메모', 'good': '조용함'},
                         {'visited': '2025년 7월', 'cost': 'JPY 24000 / 1박',
                          'booking': '조식 포함', 'experience': '창가에서 소음이 들림',
                          'audience': '역 근처 숙소를 원하는 사람',
                          'sources': '예약 내역 확인', 'disclosure': '직접 결제',
                          'related': '후쿠오카 여행'}):
                data = {'slug': 'test', 'category': 'hotel-review', 'date': '2026-09-13',
                        'info': info, 'photos': [{'name': 'a.webp', 'memo': '사진 설명', 'skip': True}]}
                path = server.write_notes(data)
                self.assertEqual(json.loads(path.with_suffix('.json').read_text()), data)
                content = path.read_text()
                for value in info.values():
                    self.assertIn(value, content)
                self.assertIn('게시 예정일: 2026-09-13', content)
                self.assertIn('한국어·영어', content)
                self.assertIn('추측하거나 만들어 채우지 않는다', content)
                self.assertIn('(이 글에서 뺌)', content)
                self.assertEqual('## 추가 확인하면 좋은 정보' in content, 'visited' not in info)

if __name__ == '__main__':
    unittest.main()
