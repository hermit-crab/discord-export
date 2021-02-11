## discord-export

Basic Discord channel archiver.

Data is stored in a jsonlines file per channel, each record is of following structure:  
```
{"type": type_of_the_record, "data": raw_api_response_data}
```  
`raw_api_response_data` is the exact data as seen in official Discord API, any synthetic fields generate by this library are prefixed with a double underscore.

For something simpler and more user friendly see https://github.com/Tyrrrz/DiscordChatExporter. Note that it is not as data comprehensive.

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
