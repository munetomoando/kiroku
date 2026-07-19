from kiroku import progress_server as ps


def test_stage_to_fraction_collect():
    assert ps.stage_to_fraction("作業を収集しています…") == 0.08


def test_stage_to_fraction_summarize_progresses_by_day():
    # 日が進むほど割合が上がり、0.12〜0.90 の範囲に収まる。
    f1 = ps.stage_to_fraction("要約を生成しています…（2日中 1日目）")
    f2 = ps.stage_to_fraction("要約を生成しています…（2日中 2日目）")
    assert 0.12 <= f1 < f2 <= 0.90


def test_stage_to_fraction_render_and_done():
    assert ps.stage_to_fraction("報告書を作成しています…") == 0.95
    assert ps.stage_to_fraction("完了") == 1.0


def test_state_fraction_is_monotonic():
    st = ps._State()
    st.update("報告書を作成しています…", 0.95)
    st.update("作業を収集しています…", 0.08)   # 逆行させない
    assert st.snapshot()["fraction"] == 0.95


def test_state_done_flag():
    st = ps._State()
    st.update("完了", 1.0, done=True)
    snap = st.snapshot()
    assert snap["done"] is True and snap["fraction"] == 1.0
