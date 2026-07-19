-- kiroku ランチャー。クリックで run-kiroku.sh を実行し、進捗ウィンドウを表示する。
-- これはテンプレート。install.sh が __KIROKU_DIR__ を実際の配置パスに
-- 置換してから osacompile でアプリを生成する（手動ビルドは README 参照）。
--
-- 仕組み: 本体を「バックグラウンド実行」し、段階ファイル(KIROKU_STAGE_FILE)を
-- ポーリングして進捗ウィンドウに現在の段階を表示。完了マーカーが出たら報告書を開く。
on run
	set kirokuDir to "__KIROKU_DIR__"
	set runScript to kirokuDir & "/run-kiroku.sh"
	set reportPath to kirokuDir & "/作業報告書.html"

	-- 進捗ウィンドウ（不定＝スピナー）。ハンドラ実行中だけ表示される。
	set progress total steps to -1
	set progress description to "kiroku を実行中…"
	set progress additional description to "作業を収集しています…"

	-- 段階テキスト用と完了マーカー用の一時ファイル。
	set stageFile to (do shell script "mktemp /tmp/kiroku_stage.XXXXXX")
	set doneFile to stageFile & ".done"

	try
		-- 本体をバックグラウンド実行（KIROKU_OPEN=0 で本体側の自動オープンを抑止）。
		-- 完了時に doneFile を作る。出力は捨てて即座に制御を戻す。
		set envPrefix to "export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; export KIROKU_OPEN=0; export KIROKU_STAGE_FILE=" & quoted form of stageFile & "; "
		do shell script envPrefix & "{ " & quoted form of runScript & " ; echo done >" & quoted form of doneFile & " ; } >/dev/null 2>&1 &"

		-- 完了まで待ちつつ、段階ファイルの内容を進捗ウィンドウへ反映。
		repeat
			delay 0.4
			if (do shell script "test -f " & quoted form of doneFile & " && echo y || echo n") is "y" then exit repeat
			try
				set stageText to (do shell script "cat " & quoted form of stageFile)
				if stageText is not "" then set progress additional description to stageText
			end try
		end repeat
	on error errMsg number errNum
		display notification ("エラー: " & errMsg) with title "kiroku 実行失敗"
	end try

	-- 一時ファイルを後片付け。
	do shell script "rm -f " & quoted form of stageFile & " " & quoted form of doneFile

	-- 手動クリック時は、新しい作業が無くても既存の報告書を必ず開く。
	set hasReport to (do shell script "test -f " & quoted form of reportPath & " && echo yes || echo no")
	if hasReport is "yes" then
		do shell script "open " & quoted form of reportPath
	else
		display notification "まだ報告書がありません（作業記録が貯まると生成されます）" with title "kiroku"
	end if
end run
