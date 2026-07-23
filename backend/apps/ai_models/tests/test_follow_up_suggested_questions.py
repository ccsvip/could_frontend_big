from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from apps.ai_models.services.follow_up_suggested_questions import (
    generate_follow_up_suggested_questions,
    _parse_question_list,
)


class FollowUpSuggestedQuestionsServiceTests(SimpleTestCase):
    def test_disabled_returns_empty(self):
        model = MagicMock()
        result = generate_follow_up_suggested_questions(
            model=model,
            history_messages=[{'role': 'user', 'content': '你好'}],
            latest_answer='你好，有什么可以帮你？',
            enabled=False,
        )
        self.assertEqual(result, [])

    def test_empty_answer_returns_empty(self):
        model = MagicMock()
        result = generate_follow_up_suggested_questions(
            model=model,
            history_messages=[],
            latest_answer='   ',
            enabled=True,
        )
        self.assertEqual(result, [])

    def test_missing_model_returns_empty(self):
        result = generate_follow_up_suggested_questions(
            model=None,
            history_messages=[],
            latest_answer='回复',
            enabled=True,
        )
        self.assertEqual(result, [])

    @patch('apps.ai_models.services.follow_up_suggested_questions.llm_services.run_llm_chat_completion')
    def test_happy_path_parses_json_array(self, mock_completion):
        mock_completion.return_value = '["续航怎么样？","有哪些颜色？","价格是多少？"]'
        model = MagicMock()
        result = generate_follow_up_suggested_questions(
            model=model,
            history_messages=[
                {'role': 'user', 'content': '介绍一下手机'},
                {'role': 'assistant', 'content': '这是一款旗舰手机。'},
            ],
            latest_answer='这是一款旗舰手机。',
            enabled=True,
        )
        self.assertEqual(result, ['续航怎么样？', '有哪些颜色？', '价格是多少？'])
        mock_completion.assert_called_once()
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs['temperature'], 0.2)
        # 主对话 messages 不应被外部传入；服务自己构造独立 messages
        self.assertEqual(len(kwargs['messages']), 2)
        self.assertEqual(kwargs['messages'][0]['role'], 'system')

    @patch('apps.ai_models.services.follow_up_suggested_questions.llm_services.run_llm_chat_completion')
    def test_bad_json_returns_empty(self, mock_completion):
        mock_completion.return_value = 'not a json array'
        model = MagicMock()
        result = generate_follow_up_suggested_questions(
            model=model,
            history_messages=[],
            latest_answer='回复内容',
            enabled=True,
        )
        self.assertEqual(result, [])

    @patch('apps.ai_models.services.follow_up_suggested_questions.llm_services.run_llm_chat_completion')
    def test_exception_returns_empty(self, mock_completion):
        mock_completion.side_effect = RuntimeError('boom')
        model = MagicMock()
        result = generate_follow_up_suggested_questions(
            model=model,
            history_messages=[],
            latest_answer='回复内容',
            enabled=True,
        )
        self.assertEqual(result, [])

    def test_parse_question_list_caps_three_and_truncates(self):
        raw = '["一","二","三","四","' + ('超长问题' * 20) + '"]'
        parsed = _parse_question_list(raw)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0], '一')
