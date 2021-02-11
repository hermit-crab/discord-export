## discord-export

Basic discord channel archiver. Data is stored in a jsonlines file per channel, each record is of following structure `{"type": type_of_the_record, "data": raw_api_response_data}`. `raw_api_response_data` has the exact response as seen from official Discord API, any synthetic data generate by this library are prefixed with a double underscore.

For something simpler and potentially more user friendly see https://github.com/Tyrrrz/DiscordChatExporter. Note that is not as data comprehensive however.

#### Requirements
* Python3.6

#### Installation
```bash
> pip3 install https://github.com/hermit-crab/discord-export/archive/master.zip --user
```

#### Usage
```bash
> discord-export export-channel NNNNNNNNNNNNNN -t YOUR_TOKEN
> discord-export export-channel --help # to see all options
# can also be run as module
> python3 -m discord_export ...
```
