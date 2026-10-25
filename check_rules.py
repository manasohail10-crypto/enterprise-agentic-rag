import re

from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS

users = set(re.findall(r"^define user (.+)$", COLANG_CONTENT, re.M))
bots = set(re.findall(r"^define bot (.+)$", COLANG_CONTENT, re.M))
flows = re.findall(r"^define flow (.+)\n  user (.+)\n  bot (.+)$", COLANG_CONTENT, re.M)

for name, user, bot in flows:
    print(name, "OK" if user in users and bot in bots else "BROKEN")

messages = re.findall(r'^define bot .+\n  "(.+)"$', COLANG_CONTENT, re.M)
for message in messages:
    found = any(item in message for item in RAIL_INDICATORS)
    print("indicator found" if found else "NO INDICATOR", "-", message[:45])