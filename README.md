# Nuskslavian Template Stealer
## The Story
[SKIP TO INSTALL INSTRUCTIONS](#Install-Instructions)

Hello there! I'm Collared, and if you dont know me, I am a programmer, and former Administration Chairman of the Lunarianity Ascendancy of Nuskslavia. A couple of months ago, I resigned under not so perfect conditions, but I continued coding for Nuskslavia, as I was promised $150 in exchange for giving Tzarissimus the code for a nukebot, and finishing his website.

Originally, he only promised $150 for when I finished the website, to be paid in 10 months of nitro and $50 in cash, but later we changed the deal, so that payments would start immediately, and I would give him the nukebot code.

A few days later, Tzarissimus found out that I had shared the Nuskslavian server template to a friend, and that friend had passed it on. I did not intend on this, but as a compromise, I gave him my server template stealer as well, and all continued as normal. I had taken the server template as collateral, just in case he betrayed or tried to cheat me, and I had not expected said friend to leak it, though only 2 people used it.

He gave me one month of nitro, but then on July 17, everything changed, when he broke his half of the deal, called me a traitor, and refused to pay me any more. Basically, Tzarissimus took advantage of me, a 13 year old, making me code for 35+ hours, which I was fine with, but then cheating me out of the $145 that he had promised me.

Tzarissimus will try to say I used AI for all of it, but the truth is, I did not. I used AI for the template stealer, as it was a selfbot, and I didnt know how to make one, and debugging some of the nukebot, bugs I couldn’t resolve, but the rest of it was me, including the 21 hours on the website. The template stealer only took about 3 total, so 32 hours was just me coding.
## Install Instructions
1. if you havent already, [install python](https://www.python.org/downloads/)
2. go to Command Prompt (or terminal on mac)
3. type the following command:
`pip install discord.py aiohttp`
4. download the repository files `bot.py` and `selfbot.py` IT IS IMPORTANT THAT selfbot.py REMAIN NAMED **EXACTLY** THAT.
5. put bot.py and selfbot.py in a folder together in your documents folder
6. go into bot.py and edit the selfbot token to your discord token (look up how to find your token if you dont know)
7. edit the loadbot token into a discord bot token from the discord developer portal
8. rename bot.py to whatever you want
9. IF YOU ARE ON WINDOWS:
in the Command Prompt run the following command:
`cd C:/Users/YOUR_USERNAME/Documents/WHATEVER_THE_FOLDER_IS_CALLED`
IF YOU ARE ON MAC:
in the terminal run the following command:
`cd ~/Documents/WHATEVER_THE_FOLDER_IS_CALLED`
10. run the following command:
`python bot.py` OR if you have changed the name of your file, do `python YOUR FILE NAME`.
11. go to discord
12. run the following command in a server:
`!ping`
13. it will delete your message and do nothing. THIS IS INTENTIONAL. if you look in the console you will see it printing shit
14. once its done, it will give you a link to invite the bot to load stuff
15. invite that bot to a BLANK SERVER
16. type !restore
17. the roles are reversed. THIS IS INTENTIONAL. it is due to a glitch with discord where, when making a template via the API, discord will reverse the roles, and put the bottom role on top, etc. if you want to have the roles normal, but reversed in the template, do `!reverseroles`

**To run it again after closing the terminal/command prompt, redo steps 8-17.**

**If you have any questions, dm me at `c0llared_` on discord.**
