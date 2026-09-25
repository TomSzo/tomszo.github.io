# -*- coding: utf-8 -*-
"""Időjárás (Időkép + Open-Meteo) - Kodi időjárás-szolgáltató belépési pont."""
import sys

from resources.lib import weather

if __name__ == '__main__':
    weather.main(sys.argv[1:])
