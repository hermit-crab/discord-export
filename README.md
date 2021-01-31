## discord-export **[UNMAINTAINED]**
Discord channel archiver

**[UNMAINTAINED]** - good active alternative: https://github.com/Tyrrrz/DiscordChatExporter

#### Requirements
* Python3.5

#### Installation
```bash
> pip3 install https://github.com/Unknowny/discord-export/archive/master.zip --user --process-dependency-links
```

#### Usage
```bash
# this will run an interactive mode (or add "--help" to get help for avalable options)
> discord-export
# can also be run as
> python3 -m discord_export
```

#### Output format
Output server/channel/dm dump is a csv feed in a form:
```
record-type,json-data
...
```
Can be worked over like this:
```python
import json

with open('chatlog.records') as f:
    for line in f:
        record_type, data = line.split(',', 1)
        if record_type == 'message':
            message = json.loads(data)
            print(message['content'])
```
