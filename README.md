# TitaLatexBot
Telegram Bot that receive an LaTeX equation and send it back as a sticker.

This is developed with [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) using the listener mechanism. This fork has been modified for my own usage, because I could not find a latex bot still working.

## Required packages

You need to install previously **libwebp**, **Pillow** and **pyTelegramBotAPI**. It's very important you get libwebp **BEFORE** pillow (or you can re-install pillow after installing libwebp). You can get them using your package manager.

In Archlinux
```
pacman -S libwebp python-pillow
```

In Debian-based distros
```
apt-get install libwebp2 libwebp-dev
```

On MacOs
```
brew install webp
```

Using pip
```
python3 -m pip install --upgrade Pillow
python3 -m pip install --upgrade pyTelegramBotAPI
```

## Usage

1. Create a bot with the BotFather Telegram Bot
2. Write the token in token.txt file
3. Execute the bot in your server with ```./bot.py```
4. In the Telegram client you can talk with your bot or add them to groups. All messages beggining with **/latex** or @aliasofyourbot will be catched by your bot.

## Example

![Examples from the original dev mobile](example.png)

Enjoy it!
