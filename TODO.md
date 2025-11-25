# Task Manager Priority Label Update

## Steps:
- [ ] 1. Update templates/dashboard.html: Replace {{ t.priority }} in badge with Jinja mapping to display Timely/Prompt/Immediate while keeping backend value and classes unchanged.
- [ ] 2. Update templates/create_task.html: Add value="Low"/"Medium"/"High" to priority select options (display Timely/Prompt/Immediate), keep selected on Medium equiv.
- [ ] 3. Update templates/edit_task.html: Add value="Low"/"Medium"/"High" to options, fix selected conditions to match backend 'Low'/'Medium'/'High'.
- [ ] 4. Check other potential files (templates/home.html, templates/inbox.html, static/js/main.js, static/style.css, static/custom.css) for priority labels using read_file or search_files.
- [ ] 5. Test: Run Flask app, use browser_action to verify UI labels, form submissions save correct backend values, sorting/filtering intact.
- [ ] 6. Update TODO.md as complete and attempt_completion.
