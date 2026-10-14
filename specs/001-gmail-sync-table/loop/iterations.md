# Maker Iterations

Append-only. One record per /speckit.loop.run iteration. The maker never marks
the loop done — it records what it attempted and which criteria it believes are
now ready for the checker.

<!-- Record format:
## Iteration <n> — <date>
- Targeted criteria: <D-ids>
- Change: <what was produced/modified, with file pointers>
- Maker self-assessment: <which criteria the maker believes are now ready>
- Open questions / risks: <anything the checker or a human should look at>
- Handoff: ready-for-check
-->
