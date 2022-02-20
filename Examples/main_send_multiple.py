import  framework, secret
from framework import discord



############################################################################################
#                               GUILD MESSAGES DEFINITION                                  #
############################################################################################

# File object representing file that will be sent
l_file1 = framework.FILE("./Examples/main_send_file.py")
l_file2 = framework.FILE("./Examples/main_send_multiple.py")

## Embedded
l_embed = framework.EMBED(
author_name="Developer",
author_icon="https://solarsystem.nasa.gov/system/basic_html_elements/11561_Sun.png",
fields=\
    [
        framework.EMBED_FIELD("Test 1", "Hello World", True),
        framework.EMBED_FIELD("Test 2", "Hello World 2", True),
        framework.EMBED_FIELD("Test 3", "Hello World 3", True),
        framework.EMBED_FIELD("No Inline", "This is without inline", False),
        framework.EMBED_FIELD("Test 4", "Hello World 4", True),
        framework.EMBED_FIELD("Test 5", "Hello World 5", True)
    ]
)


guilds = [
    framework.GUILD(
        guild_id=123456789,                                 # ID of server (guild)
        messages_to_send=[                                  # List MESSAGE objects
            framework.MESSAGE(
                              start_period=None,            # If None, messages will be send on a fixed period (end period)
                              end_period=15,                # If start_period is None, it dictates the fixed sending period,
                                                            # If start period is defined, it dictates the maximum limit of randomized period
                              data=["Hello World",          # Data you want to sent to the function (Can be of types : str, embed, file, list of types to the left
                                    l_file1,                # or function that returns any of above types(or returns None if you don't have any data to send yet),
                                    l_file2,                # where if you pass a function you need to use the framework.FUNCTION decorator on top of it ).
                                    l_embed],           
                              channel_ids=[123456789],      # List of ids of all the channels you want this message to be sent into
                              mode="send",          # Clear all discord messages that originated from this MESSAGE object
                              start_now=True                # Start sending now (True) or wait until period
                              ),  
        ],
        generate_log=True           ## Generate file log of sent messages (and failed attempts) for this server 
    )
]

                                     
############################################################################################

if __name__ == "__main__":
    framework.run(  token=secret.C_TOKEN,           # MANDATORY,
                    server_list=guilds,             # MANDATORY
                    is_user=False,                  # OPTIONAL
                    user_callback=None,             # OPTIONAL
                    server_log_output="History",    # OPTIONAL
                    debug=True)                     # OPTIONAL