-- Sends a message to an existing chat by GUID.
-- Text arrives via argv so quotes/newlines never need escaping.
on run argv
	set chatId to item 1 of argv
	set msgText to item 2 of argv
	tell application "Messages"
		send msgText to chat id chatId
	end tell
end run
