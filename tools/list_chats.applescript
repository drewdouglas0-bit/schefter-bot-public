-- Lists every chat Messages.app knows about, so you can find your league's GUID.
-- Group chats are the ones whose id contains "chat" and have 2+ participants.
tell application "Messages"
	set out to ""
	repeat with c in chats
		set chatName to "(unnamed)"
		try
			if name of c is not missing value then set chatName to name of c
		end try
		set who to ""
		try
			set handles to {}
			repeat with p in participants of c
				set end of handles to (handle of p)
			end repeat
			set AppleScript's text item delimiters to ", "
			set who to handles as text
			set AppleScript's text item delimiters to ""
		end try
		set out to out & (id of c) & tab & chatName & tab & who & linefeed
	end repeat
	return out
end tell
