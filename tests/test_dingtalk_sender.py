import unittest
import json
from unittest.mock import patch, MagicMock
from src.notification_sender.dingtalk_sender import DingtalkSender
from src.config import Config

class TestDingtalkSender(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.dingtalk_webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=test_token"
        self.config.dingtalk_secret = "test_secret"
        self.sender = DingtalkSender(self.config)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        result = self.sender.send_to_dingtalk("Test content", "Test Title")
        self.assertTrue(result)
        mock_post.assert_called_once()
        
        called_url = mock_post.call_args[0][0]
        self.assertIn("timestamp=", called_url)
        self.assertIn("sign=", called_url)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_chunked_long_chinese_message_payload_size(self, mock_post):
        """測試超過 20KB 限制的多字節中文長文本與長標題，驗證實際發送的 JSON payload 字節數嚴格遵守限制"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # 生成超長中文內容 (每個漢字 3 bytes，生成約 30,000 bytes 的文本)
        long_chinese_content = "股票复盘" * 2500 
        # 生成極端長標題
        long_title = "这是一个用来测试钉钉机器人极端边界情况的超长超长超长超长标题" * 10 

        result = self.sender.send_to_dingtalk(long_chinese_content, long_title)
        
        self.assertTrue(result)
        # 應該被切分成至少 2 個請求
        self.assertGreaterEqual(mock_post.call_count, 2)
        
        # 驗證每次請求的 JSON 實際序列化字節數絕對不超過 DingTalk 的 20000 字節限制
        for call in mock_post.call_args_list:
            payload = call.kwargs['json']
            # 模擬實際網絡傳輸時的 JSON 序列化 (無空格，UTF-8編碼)
            payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            
            # 斷言：最終發送的整個 JSON 請求體 <= 20000 字節
            self.assertLessEqual(payload_bytes, 20000, f"Payload 字节数为 {payload_bytes}，超过钉钉 20KB 限制！")
            
            # 確保標題被成功截斷並沒有丟失分頁信息
            self.assertLessEqual(len(payload['markdown']['title']), 120)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_api_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 310000, "errmsg": "invalid token"}
        mock_post.return_value = mock_response

        result = self.sender.send_to_dingtalk("Test content")
        self.assertFalse(result)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_exception(self, mock_post):
        mock_post.side_effect = Exception("Network Error")
        result = self.sender.send_to_dingtalk("Test content")
        self.assertFalse(result)

    @patch("src.notification_sender.dingtalk_sender.requests.post")
    def test_send_strips_hidden_market_region_metadata(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        result = self.sender.send_to_dingtalk("[dsa-market-region]: # (cn)\n\n# 🎯 Market Review\n\nBody")

        self.assertTrue(result)
        payload = mock_post.call_args.kwargs["json"]
        self.assertNotIn("[dsa-market-region]", payload["markdown"]["text"])
        self.assertIn("# 🎯 Market Review", payload["markdown"]["text"])
        self.assertIn("Body", payload["markdown"]["text"])
