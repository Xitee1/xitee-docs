---
title: Xite SMP Minecraft server
description: Xite SMP is a small public Minecraft survival server, running since 2020. Live server status, rules and how to join.
template: minecraft.html
hide:
  - navigation
---

<!-- Heading and intro on the left, status box on the right; stacked on narrow screens -->
<div class="mc-intro">
  <div class="mc-intro__text">
    <h1>Xite SMP</h1>
    <p>A small survival server that has been running since around December 2020. There isn't much going on, most of the time it's empty, and even I don't join it very often anymore. But it's running. And it's going to stay that way.</p>
  </div>
  <div class="mc-status" data-mc-status="mc.xitma.de">
    <div class="mc-status__header">Server status</div>
    <dl class="mc-status__rows">
      <div class="mc-status__row">
        <dt>Status</dt>
        <dd class="mc-status__state" data-mc-field="status">–</dd>
      </div>
      <div class="mc-status__row">
        <dt>Players online</dt>
        <dd data-mc-field="players">–</dd>
      </div>
      <div class="mc-status__row">
        <dt>Version</dt>
        <dd data-mc-field="version">–</dd>
      </div>
      <div class="mc-status__row">
        <dt>Address</dt>
        <dd>
          mc.xitma.de
          <button class="mc-status__copy" type="button" data-mc-copy="mc.xitma.de" title="Copy address" aria-label="Copy address">
            <svg class="mc-status__copy-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 21H8V7h11m0-2H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2m-3-4H4a2 2 0 0 0-2 2v14h2V3h12z"/></svg>
            <svg class="mc-status__done-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21 7 9 19l-5.5-5.5 1.41-1.41L9 16.17 19.59 5.59z"/></svg>
          </button>
        </dd>
      </div>
    </dl>
    <div class="mc-status__footer">Live via <a href="https://mcstatus.io">mcstatus.io</a> · refreshed every 60 s</div>
  </div>
</div>

## The server

Xite SMP is a plain survival server without a big concept. Just go find yourself a spot, build and do whatever you like. The community has always been small and friendly. It's mostly German-speaking, but English speakers are just as welcome. People build next to each other instead of hiding far apart, as you'd usually do for fear of griefing. There are no plots either.

The rules are simple: Be nice, don't be a dick. Apart from cheating (X-ray included) or hacking, do whatever you want, as long all participants are fine with it.

The server is public and there's no whitelist, so anyone can join. New players start with limited permissions, though, and can only walk around at first. If you want to build, you have to ask for permissions on the Discord server. From there, a trust level system unlocks more permissions over time.

## How to join

1. Start Minecraft (Java Edition). The matching version is shown in the status box above.
2. Go to Multiplayer → "Add Server".
3. Enter `mc.xitma.de` as the server address. That's it.

## Tech

- [BlueMap](http://mc.xitma.de:8100): the whole world as a map in your browser.
- CoreProtect logs every block change. The statistics are visible to everyone on purpose. It's just interesting to see when what happened.
- A custom SMP plugin tweaks small things, such as the Discord integration.
- Regular backups.
