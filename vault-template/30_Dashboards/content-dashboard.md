---
title: Content Dashboard
type: dashboard
created: 2026-06-30
tags: [dashboard, chubbyskills]
---

# Content Dashboard

## Recent Captures

```dataview
TABLE platform, created, content_type, source
FROM "00_Inbox" OR "10_Sources"
SORT created DESC
LIMIT 20
```

## By Platform

```dataview
TABLE rows.file.link AS Notes
FROM "00_Inbox" OR "10_Sources" OR "20_Processed"
GROUP BY platform
SORT length(rows) DESC
```

## Needs Processing

```dataview
TABLE platform, created, source
FROM "00_Inbox"
WHERE !summary
SORT created DESC
```
