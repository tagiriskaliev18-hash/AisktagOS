"""MindKit — общие службы экосистемы MindTagSystem в духе Apple.

Что внутри (аналог у Apple — модуль):

* Связка ключей (Keychain)           — ``mindkit.keychain``
* Единые настройки (iCloud-настройки) — ``mindkit.config``
* MindLink: общий буфер обмена, Handoff, AirDrop, уведомления
  на всех устройствах пользователя    — ``mindkit.link``
* Центр уведомлений                   — ``mindkit.notify``
* Поиск по всему (Spotlight)          — ``mindkit.search``
* Быстрые команды (Shortcuts)         — ``mindkit.shortcuts``
* Ассистент Mind (Siri)               — ``mindkit.assistant``
* Каталог приложений (App Store)      — ``mindkit.store``
* Единый дизайн Aurora (HIG)          — ``mindkit.design``

Только стандартная библиотека Python 3.10+. Если установлены ``keyring``
и ``cryptography``, MindKit использует их: ключи уходят в системное
хранилище, а трафик MindLink шифруется.
"""

__version__ = "0.1.0"
