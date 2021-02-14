## discord-export

Basic Discord chats archiver.

Data is stored in a jsonlines file per channel, each record is of following structure:  
```
{"type": type_of_the_record, "data": raw_api_response_data, "ts": timestamp}
```  
- `raw_api_response_data` is the API data as seen in official Discord API.
- `timestamp` is a standard unix timestamp of when the record was created.

For something more user friendly see https://github.com/Tyrrrz/DiscordChatExporter (not as data comprehensive).

#### Requirements
* Python3.6

#### Installation
```bash
# via pipx (isolated python apps installer, recommended)
> pipx install https://github.com/hermit-crab/discord-export/archive/master.zip
# via pip (general python packages installer)
> pip3 install https://github.com/hermit-crab/discord-export/archive/master.zip --user
```

#### Usage
```bash
> discord-export export-channel NNNNNNNNNNNNNN -t YOUR_TOKEN
> discord-export export-channel --help # to see all options
> discord-export --help # to see all commands
# can also be run as module
> python3 -m discord_export ...
# you can view the created file as plaintext chatlog
> discord-export render ./SomeGuild.SomeChannel.jl
# which outputs something like
** archive initiator: SomeGuy#7777 (NNNNNNNNNNNNNN)
** channel: big-room (NNNNNNNNNNNNNN)
** server: Goodfellas (NNNNNNNNNNNNNN)
2021-02-12 18:33:37 Jack: hey sup 👋
2021-02-12 18:33:49 Dood: nothin much
2021-02-12 18:33:49 Jack: same here :peepo:
                    [reacts: 👌x4, 🤷]
2021-02-12 18:33:49 Mate: cool!
...
```

#### Notes
- Any synthetic fields placed by this library into `raw_api_response_data` are prefixed with a double underscore.
- Cleaned up message content can be accessed under "__clean_content" field.
- Users who reacted to a message are also archived but not more than 100 users per reaction.
    - This slow things down considerably given it makes a request for every reaction. If you don't need it, use `--skip-reaction-users` flag.
- No new development is planned (unless something breaks) as I've implemented everything I personally needed. But feel free to open an issue with feedback. 
- Regarding usage of account tokens see token related questions at https://github.com/Tyrrrz/DiscordChatExporter/wiki/Troubleshooting#general.
  - There exists a fancier / safer method of auth (OAuth2) in theory but I can't be bothered adding all that.
