# BD Pipeline Agent: Command Reference

## Quick Commands (Copy/Paste Ready)

### Starting a Pipeline
```
Pull all emails from [contact name] and identify companies they want intros to.
```
```
Here's a new prospect list from Scott: [paste list]. Run the full pipeline for Tivly.
```
```
Add these companies to the Tivly pipeline: [company1], [company2], [company3]
```

### Relationship Intelligence
```
Run relationship check on [company name].
```
```
Who do I know at [company name]? Check Gmail, HubSpot, Calendar, AIR attendees, and my relationship map.
```
```
Check all 16 companies for warm paths. Show me the full five-source scan.
```

### Scoring
```
Score these companies for Tivly.
```
```
Score the pipeline for [client name].
```
```
Reweight to 80/20 fit over relationship.
```
```
Reweight to 30/70 relationship first.
```

### Intro Packages
```
Prep intro for [company name].
```
```
Write the intro email for [contact name] at [company name].
```
```
Generate intro packages for my top 3 hot-tier companies.
```

### Pipeline Management
```
Pipeline status.
```
```
Which companies moved tiers since last check?
```
```
Show me all companies with RS 0 but PMF above 70.
```

### Updating Relationships
```
I just met [name] at [company]. They're [title]. Met them at [event]. Add as a [score].
```
```
Bump [company] from 0 to 2. I connected with [name] on LinkedIn.
```
```
Update: [name] at [company] responded to my email. Move to RS 3.
```

### Switching Clients
```
Score these same companies for Circle AI instead of Tivly.
```
```
Profile [new client name], then score the pipeline for them.
```

### Cross-Referencing
```
Cross-reference the Tivly pipeline against the AIR 2025 attendee list.
```
```
Check Scott's latest email for new target companies and add them to the pipeline.
```
```
Which of my top 20 matches have contacts at the same upcoming conferences as me?
```

## Five-Source Scan Order
1. **Gmail** - Email threads with company domains and names
2. **HubSpot** - CRM contacts and company records
3. **Google Calendar** - Past meetings and shared events
4. **Conference Lists** - AIR 2025 and any other uploaded rosters
5. **Relationship Map** - Project file with manually tracked connections

## Scoring Quick Reference
- **Matchmaker Score** = (PMF x 0.6) + (RS x 0.4) [default weights]
- **PMF** = Weighted sum of client-specific criteria, normalized to 0-100
- **RS** = Relationship Strength (0-5), scaled to 0-100
- **Hot** = 70+ | **Warm** = 50-69 | **Monitor** = 30-49 | **Pass** = <30
