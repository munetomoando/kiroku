from pathlib import Path
from kiroku import gather

FIX = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


def test_iter_records_skips_broken_lines():
    recs = list(gather.iter_records([FIX]))
    assert len(recs) == 5  # 6 行中 1 行は壊れているのでスキップ


def test_project_name_from_cwd():
    recs = list(gather.iter_records([FIX]))
    assert gather.project_name(recs[0]) == "companion"


def test_user_prompt_text_only_real_prompts():
    recs = list(gather.iter_records([FIX]))
    # 0: 本物のプロンプト
    assert gather.user_prompt_text(recs[0]) == "ログイン画面を作って"
    # 2: tool_result はユーザー指示ではない
    assert gather.user_prompt_text(recs[2]) is None
    # 3: サイドチェーンは除外
    assert gather.user_prompt_text(recs[3]) is None


def test_assistant_texts_extracts_text_blocks_only():
    recs = list(gather.iter_records([FIX]))
    assert gather.assistant_texts(recs[1]) == ["ログイン画面を実装しました。"]
    assert gather.assistant_texts(recs[4]) == []  # tool_use のみ
