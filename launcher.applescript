-- kiroku ランチャー。クリックで進捗サーバを起動し、円形リングの進捗画面を開く。
-- これはテンプレート。install.sh が __KIROKU_DIR__ を実際の配置パスに
-- 置換してから osacompile でアプリを生成する（手動ビルドは README 参照）。
--
-- 仕組み: progress_server.py を localhost で起動 → ブラウザで進捗画面を表示。
-- サーバが run-kiroku.sh を実行し、完了で同じタブを報告書に切り替える。
-- サーバ起動に失敗した場合は、従来どおり本体を実行して報告書をファイルで開く。
on run
	set kirokuDir to "__KIROKU_DIR__"
	set runScript to kirokuDir & "/run-kiroku.sh"
	set reportPath to kirokuDir & "/作業報告書.html"
	set serverPy to kirokuDir & "/progress_server.py"
	set envPrefix to "export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; "
	set urlFile to (do shell script "mktemp /tmp/kiroku_url.XXXXXX")
	try
		-- 進捗サーバをバックグラウンド起動（URL を urlFile に書き出す）。
		set cmd to envPrefix & "nohup python3 " & quoted form of serverPy & ¬
			" --run-script " & quoted form of runScript & ¬
			" --report " & quoted form of reportPath & ¬
			" --url-file " & quoted form of urlFile & " >/dev/null 2>&1 &"
		do shell script cmd
		-- URL が書き込まれるまで待つ（最大 ~5 秒）。
		set theURL to ""
		repeat 50 times
			delay 0.1
			set theURL to (do shell script "cat " & quoted form of urlFile)
			if theURL is not "" then exit repeat
		end repeat
		if theURL is "" then error "進捗サーバの起動に失敗しました"
		open location theURL
	on error errMsg number errNum
		-- フォールバック: 本体を同期実行し、報告書をファイルで開く。
		try
			do shell script envPrefix & "export KIROKU_OPEN=0; " & quoted form of runScript & " >/dev/null 2>&1"
		end try
		set hasReport to (do shell script "test -f " & quoted form of reportPath & " && echo yes || echo no")
		if hasReport is "yes" then
			do shell script "open " & quoted form of reportPath
		else
			display notification ("kiroku 実行失敗: " & errMsg) with title "kiroku"
		end if
	end try
	do shell script "rm -f " & quoted form of urlFile
end run
