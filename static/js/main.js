// Basic client-side validation and AJAX toggles
document.addEventListener('click', function(e) {
  if (e.target && e.target.classList.contains('toggle-complete')) {
    e.preventDefault();
    let btn = e.target;
    let parent = btn.closest('form');
    let taskId = btn.getAttribute('data-id');
    fetch(`/task/${taskId}/toggle_complete`, {method:'POST'}).then(r=>r.json()).then(data=>{
      if (data.ok) {
        btn.textContent = data.completed ? 'Undo' : 'Complete';
        btn.classList.toggle('btn-success', data.completed);
      } else {
        alert('Could not toggle: ' + (data.message||''));
      }
    });
  }
});

// client-side required field check for create task
const tf = document.getElementById('taskForm');
if (tf) {
  tf.addEventListener('submit', function(e) {
    const title = tf.querySelector('[name=title]').value.trim();
    const estimate = parseFloat(tf.querySelector('[name=estimate_hours]').value);
    if (title.length < 3) {
      e.preventDefault();
      alert('Title must be at least 3 characters.');
      return;
    }
    if (!estimate || estimate <= 0) {
      e.preventDefault();
      alert('Estimate must be a positive number.');
      return;
    }
  });
}

// Dynamic notifications
function loadNotifications() {
  fetch('/api/notifications')
    .then(response => response.json())
    .then(data => {
      const dropdown = document.getElementById('notificationDropdown');
      const badge = dropdown.querySelector('.badge');
      const menu = dropdown.nextElementSibling;
      const unreadCount = data.filter(n => !n.is_read).length;
      badge.textContent = unreadCount;
      badge.style.display = unreadCount > 0 ? 'inline' : 'none';

      const header = menu.querySelector('.dropdown-header');
      header.nextElementSibling.innerHTML = '';
      data.slice(0, 5).forEach(notification => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.className = 'dropdown-item';
        a.href = '#';
        a.textContent = notification.message;
        if (!notification.is_read) {
          a.classList.add('fw-bold');
        }
        a.addEventListener('click', () => markAsRead(notification.id));
        li.appendChild(a);
        header.parentNode.insertBefore(li, header.nextElementSibling.nextElementSibling);
      });
      if (data.length > 5) {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.className = 'dropdown-item text-center';
        a.href = '#';
        a.textContent = 'View all notifications';
        li.appendChild(a);
        menu.appendChild(li);
      }
    });
}

function markAsRead(notificationId) {
  fetch(`/api/notifications/${notificationId}/read`, { method: 'POST' })
    .then(() => loadNotifications());
}

// Load notifications on page load
document.addEventListener('DOMContentLoaded', loadNotifications);

// Calendar initialization
if (document.getElementById('calendar')) {
  document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');
    var calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,timeGridDay'
      },
      events: function(fetchInfo, successCallback, failureCallback) {
        fetch('/api/tasks')
          .then(response => {
            if (!response.ok) {
              throw new Error('Failed to fetch tasks');
            }
            return response.json();
          })
          .then(data => {
            // Transform events to FullCalendar format
            var events = data.map(task => {
              var eventColor = '#2563eb'; // default blue
              if (task.priority === 'High') {
                eventColor = '#dc2626'; // red
              } else if (task.priority === 'Medium') {
                eventColor = '#d97706'; // amber
              } else if (task.priority === 'Low') {
                eventColor = '#059669'; // green
              }

              return {
                id: task.id,
                title: task.title,
                start: task.due_date, // map due_date to start
                backgroundColor: eventColor,
                borderColor: eventColor,
                textColor: '#ffffff',
                extendedProps: {
                  description: task.description,
                  priority: task.priority,
                  estimate_hours: task.estimate_hours,
                  completed: task.completed
                }
              };
            });
            successCallback(events);
          })
          .catch(error => {
            console.error('Error loading calendar events:', error);
            failureCallback(error);
          });
      },
      eventClick: function(info) {
        var task = info.event;
        var description = task.extendedProps.description || 'No description';
        var priority = task.extendedProps.priority || 'Not set';
        var estimate = task.extendedProps.estimate_hours || 'Not set';
        var completed = task.extendedProps.completed ? 'Yes' : 'No';

        alert('Task: ' + task.title +
              '\nDescription: ' + description +
              '\nPriority: ' + priority +
              '\nEstimate: ' + estimate + ' hours' +
              '\nCompleted: ' + completed);
      },
      height: 'auto',
      aspectRatio: 1.35,
      eventDisplay: 'block',
      dayMaxEvents: true,
      moreLinkClick: 'popover'
    });

    try {
      calendar.render();
    } catch (error) {
      console.error('Error rendering calendar:', error);
      calendarEl.innerHTML = '<div class="alert alert-danger">Error loading calendar. Please refresh the page.</div>';
    }
  });
}

// Search and Filter functionality
document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('search-input');
  const statusFilter = document.getElementById('statusFilter');
  const priorityFilter = document.getElementById('priorityFilter');
  const categoryFilter = document.getElementById('categoryFilter');
  const sortFilter = document.getElementById('sortFilter');

  function filterTasks() {
    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const statusValue = statusFilter ? statusFilter.value : 'all';
    const priorityValue = priorityFilter ? priorityFilter.value : 'all';
    const categoryValue = categoryFilter ? categoryFilter.value : 'all';
    const sortValue = sortFilter ? sortFilter.value : 'due_date';

    const taskCards = document.querySelectorAll('.task-card');
    const tasksArray = Array.from(taskCards);

    // Filter tasks
    tasksArray.forEach(card => {
      const title = card.querySelector('h5').textContent.toLowerCase();
      const description = card.querySelector('.task-description').textContent.toLowerCase();
      const tags = Array.from(card.querySelectorAll('.category-badge')).map(badge => badge.textContent.toLowerCase()).join(' ');
      const priority = card.querySelector('.priority-badge').textContent.toLowerCase();
      const isCompleted = card.querySelector('input.task-checkbox').checked;
      const dueDate = card.getAttribute('data-due-date') || '';

      let visible = true;

      // Search filter
      if (query && !(title.includes(query) || description.includes(query) || tags.includes(query))) {
        visible = false;
      }

      // Status filter
      if (statusValue !== 'all') {
        if (statusValue === 'completed' && !isCompleted) visible = false;
        if (statusValue === 'pending' && isCompleted) visible = false;
        if (statusValue === 'overdue' && (!dueDate || new Date(dueDate) >= new Date() || isCompleted)) visible = false;
      }

      // Priority filter
      if (priorityValue !== 'all' && !priority.includes(priorityValue.toLowerCase())) {
        visible = false;
      }

      // Category filter
      if (categoryValue !== 'all' && !tags.includes(categoryValue.toLowerCase())) {
        visible = false;
      }

      card.style.display = visible ? '' : 'none';
    });

    // Sort tasks
    const taskList = document.querySelector('.task-list');
    if (taskList) {
      const visibleTasks = tasksArray.filter(card => card.style.display !== 'none');
      visibleTasks.sort((a, b) => {
        const aDueDate = a.getAttribute('data-due-date') || '';
        const bDueDate = b.getAttribute('data-due-date') || '';
        const aPriority = a.querySelector('.priority-badge').textContent.toLowerCase();
        const bPriority = b.querySelector('.priority-badge').textContent.toLowerCase();
        const aCreated = a.getAttribute('data-created') || '';
        const bCreated = b.getAttribute('data-created') || '';

        switch (sortValue) {
          case 'due_date':
            if (!aDueDate && !bDueDate) return 0;
            if (!aDueDate) return 1;
            if (!bDueDate) return -1;
            return new Date(aDueDate) - new Date(bDueDate);
          case 'priority':
            const priorityOrder = { 'high': 0, 'medium': 1, 'low': 2 };
            return priorityOrder[aPriority] - priorityOrder[bPriority];
          case 'created':
            return new Date(bCreated) - new Date(aCreated);
          default:
            return 0;
        }
      });

      visibleTasks.forEach(task => taskList.appendChild(task));
    }
  }

  // Add event listeners
  if (searchInput) searchInput.addEventListener('input', filterTasks);
  if (statusFilter) statusFilter.addEventListener('change', filterTasks);
  if (priorityFilter) priorityFilter.addEventListener('change', filterTasks);
  if (categoryFilter) categoryFilter.addEventListener('change', filterTasks);
  if (sortFilter) sortFilter.addEventListener('change', filterTasks);
});
