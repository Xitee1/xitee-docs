---
description: PowerShell command to batch extract RAR archives across multiple subfolders using WinRAR on Windows.
---

# Extract archives within subfolders (WinRAR)

Having a lot of archived, all in their own sub-folder?


```
.
└── main-folder/
    ├── sub-folder1/
    │   └── archive.rar
    ├── sub-folder2/
    │   └── archive.rar
    ├── sub-folder3/
    │   └── archive.rar
    └── sub-folder4/
        └── archive.rar
```

You can extract all of them with this command from the `main-folder`:
```bash
dir -Recurse | % {$_.FullName} | Split-Path | Get-Unique | % {cd $_ ; & "C:\Program Files\WinRAR\Rar.exe" x *.rar}
```

I sadly can't currently say if this also works with splitted archives because it's been a while since I used this command and I no longer have a Windows PC nor subfolders with archives in them. But as far as I remember I used it for splitted archives.