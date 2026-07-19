-- kiroku ランチャー。ダブルクリックで run-kiroku.sh を実行する。
-- これはテンプレート。install.sh が __KIROKU_DIR__ を実際の配置パスに
-- 置換してから osacompile でアプリを生成する（手動ビルドは README 参照）。
on run
	set kirokuDir to "__KIROKU_DIR__"
	set runScript to kirokuDir & "/run-kiroku.sh"
	set reportPath to kirokuDir & "/作業報告書.html"
	try
		-- 復帰直後と同様に PATH を明示して本体を実行（claude / python3 を解決するため）。
		-- KIROKU_OPEN=0 で本体側の自動オープンを抑止し、この後ランチャーが必ず開く
		-- （更新の有無に関わらず、手動クリックでは常に報告書を表示する）。
		do shell script "export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; export KIROKU_OPEN=0; " & quoted form of runScript
	on error errMsg number errNum
		display notification ("エラー: " & errMsg) with title "kiroku 実行失敗"
	end try
	-- 手動クリック時は、新しい作業が無くても既存の報告書を必ず開く。
	set hasReport to (do shell script "test -f " & quoted form of reportPath & " && echo yes || echo no")
	if hasReport is "yes" then
		do shell script "open " & quoted form of reportPath
	else
		display notification "まだ報告書がありません（作業記録が貯まると生成されます）" with title "kiroku"
	end if
end run
