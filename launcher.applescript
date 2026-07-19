-- kiroku ランチャー。ダブルクリックで run-kiroku.sh を実行する。
-- ~/Desktop/kiroku.app へのビルド方法（README 参照）:
--   osacompile -o ~/Desktop/kiroku.app /Users/munetomoando/claude-work/kiroku/launcher.applescript
on run
	set kirokuDir to "/Users/munetomoando/claude-work/kiroku"
	set runScript to kirokuDir & "/run-kiroku.sh"
	try
		-- 復帰直後と同様に PATH を明示して本体を実行（claude / python3 を解決するため）
		do shell script "export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; " & quoted form of runScript
		display notification "新しい作業があれば Safari で報告書を開きます" with title "kiroku" subtitle "作業報告書を確認しました"
	on error errMsg number errNum
		display notification ("エラー: " & errMsg) with title "kiroku 実行失敗"
	end try
end run
