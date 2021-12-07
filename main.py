import asyncio
import datetime, framework,  re, os, debug, Config
from framework import GUILD, MESSAGE



def find_key(key, data):
    l_ret =  re.search(f"{key}\s*=\s*\".*?\"", data, re.DOTALL)
    if l_ret != None:
        l_ret = re.sub(f"{key}\s*=","", l_ret.group(0)).rstrip().lstrip().replace("\"", "")
    return l_ret


###########################################################################################
#                             FE UNI ADVERTISING DATA                                     #
###########################################################################################
## Configuration variables


### ARDUINO DELAVNICE


C_DATA_FILE = "delavnice_params.txt"

def find_key(key, data):
    l_ret =  re.search(f"{key}\s*:.*", data)
    if l_ret != None:
        l_ret = re.sub(f"{key}\s*:","", l_ret.group(0)).rstrip().lstrip()
    return l_ret

def get_msg():
    with open (C_DATA_FILE, 'r') as l_data_file:
        l_data_file_content = l_data_file.read()
        l_delavnice_date = [int(x) for x in find_key("datum",l_data_file_content).split("-")]
        l_content = find_key("snov", l_data_file_content)
        l_link = find_key("povezava", l_data_file_content)
        l_index   = int(find_key("indeks", l_data_file_content))
        pass
    l_time_left=(datetime.datetime(*l_delavnice_date) - datetime.datetime.now()).total_seconds()
    l_delavnice_date = f"{l_delavnice_date[2]}.{l_delavnice_date[1]}.{l_delavnice_date[0]} ob {l_delavnice_date[3]}:{l_delavnice_date[4]}"
    if l_time_left < 2 * Config.C_DAY_TO_SECOND:
        if l_time_left <= 1*Config.C_MINUTE_TO_SECOND:
            l_time_left = "Manj kot minuta"
        elif l_time_left <= 1*Config.C_HOUR_TO_SECOND:
            l_time_left = "{:.2f}".format(l_time_left/Config.C_MINUTE_TO_SECOND)  + " min"
        elif l_time_left <= 1*Config.C_DAY_TO_SECOND:
            l_time_left = "{:.2f}".format(l_time_left/Config.C_HOUR_TO_SECOND) + "h"
        else:
            l_time_left = "{:.2f}".format(l_time_left/Config.C_DAY_TO_SECOND) + "d" 
        l_embed = framework.discord.Embed()
        l_embed.add_field(name="__Arduino Delavnice__", value=f"Pridruzite se {l_index}. Arduino delavnicam", inline=False)    
        l_embed.add_field(name="Vsebina", value=f"{l_content}", inline=False)
        l_embed.add_field(name ="Datum", value=f"{l_delavnice_date}", inline=False)
        l_embed.add_field(name ="Povezava do Zooma", value=f"{l_link}", inline=False)
        return l_embed, "<@&905084973244117112>"
    return None

### SSFE OBVESTILA
CONFIG_READ_FOLDER = "Obvestila"

class FE_UNI_OBVESTILA:
    # Class variables
    stat_post_q = [] # Messages queue

    def __init__(this):
        pass
    @classmethod                        
    async def file_processor(this):
        l_files_to_remove = []
        while True:
            l_files_to_remove.clear()
            for dirname, dirs, filenames in os.walk(CONFIG_READ_FOLDER):
                for filename in filenames:
                    with open(os.path.join(dirname,filename), 'r', encoding="utf-8") as l_file:
                        try:
                            l_file_data = l_file.read()
                            # Parse date
                            l_cel_datum_parsed = find_key("DATUM", l_file_data).replace(" ", "").split("-")
                            l_datum_parsed, l_ura_parsed = l_cel_datum_parsed[0].split("."), l_cel_datum_parsed[1].split(":")
                            l_datetime = datetime.datetime(int(l_datum_parsed[2]), int(l_datum_parsed[1]), int(l_datum_parsed[0]), int(l_ura_parsed[0]),int(l_ura_parsed[1]))
                            # Parse msg
                            l_txt = find_key("SPOROCILO", l_file_data)   
                            if datetime.datetime.now() > l_datetime: # Ready to post -> push into bugger
                                
                                l_embed_msg = framework.discord.Embed()
                                l_embed_msg.add_field(name="OBVESTILO", value=l_txt, inline=False)
                                this.stat_post_q.append(l_embed_msg)   
                                l_files_to_remove.append(os.path.join(dirname,filename))
                        except Exception as ex:
                            debug.TRACE(f"Nepravilno formatiranje datotek: {filename}", debug.TRACE_LEVELS.ERROR)

                    # Remove files
                    for filename in l_files_to_remove:
                        try:
                            os.remove(filename)
                            l_files_to_remove.remove(filename)
                        finally:
                            pass
            await asyncio.sleep(5)

    @classmethod
    def get_msg(this):
        l_ret = None
        if this.stat_post_q.__len__() > 0:
            l_ret = this.stat_post_q.pop(0)
        return l_ret
    

############################################################################################
#                               GUILD MESSAGES DEFINITION                                  #
############################################################################################

GUILD.server_list = [
GUILD(
        863071397207212052,                          # ID Serverja
        # Messages
        [   #       min-sec                     max-sec      sporocilo   #IDji kanalov
            #MESSAGE(start_period=0, end_period=10 , text=FE_UNI_OBVESTILA.get_msg, channels=[863071397207212056], clear_previous=False, start_now=True)
            MESSAGE(start_period=0, end_period=1*Config.C_DAY_TO_SECOND , text=get_msg, channels=[863071397207212056], clear_previous=True, start_now=True)
        ]
    )
]
                                     
############################################################################################

def main():
    pass#asyncio.gather(asyncio.create_task(FE_UNI_OBVESTILA.file_processor()))

if __name__ == "__main__":
    framework.run(user_callback=main)
    