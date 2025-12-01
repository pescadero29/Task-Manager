// Chart data from server - rendered by Jinja2
const chartData = document.getElementById('chartData');
const weeklyProgressData = JSON.parse(chartData.getAttribute('data-weekly-progress'));
const categoriesData = JSON.parse(chartData.getAttribute('data-categories'));

// Initialize progress bars and charts
document.addEventListener('DOMContentLoaded', function() {
    // Set progress bar widths
    document.querySelectorAll('.progress-bar[data-width]').forEach(bar => {
        const width = bar.getAttribute('data-width');
        bar.style.width = width + '%';
    });

    // Weekly Progress Chart
    const weeklyCtx = document.getElementById('weeklyProgressChart').getContext('2d');
    const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    new Chart(weeklyCtx, {
        type: 'line',
        data: {
            labels: daysOfWeek,
            datasets: [{
                label: 'Tasks Completed',
                data: weeklyProgressData,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });

    // Category Chart
    const categoryCtx = document.getElementById('categoryChart').getContext('2d');
    const categoryLabels = Object.keys(categoriesData);
    const categoryValues = Object.values(categoriesData);

    // Color palette for categories
    const colors = [
        '#2563eb', '#059669', '#dc2626', '#6b7280',
        '#7c3aed', '#ea580c', '#0891b2', '#be123c'
    ];

    new Chart(categoryCtx, {
        type: 'doughnut',
        data: {
            labels: categoryLabels.length > 0 ? categoryLabels : ['No categories'],
            datasets: [{
                data: categoryValues.length > 0 ? categoryValues : [1],
                backgroundColor: colors.slice(0, Math.max(categoryLabels.length, 1))
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
});

// Task management functions
let taskToDelete = null;

function toggleTaskComplete(taskId) {
    fetch(`/task/${taskId}/toggle_complete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
    })
    .then(response => response.text())
    .then(() => {
        window.location.reload();
    })
    .catch(error => console.error('Error:', error));
}

function deleteTask(taskId) {
    taskToDelete = taskId;
    const modal = new bootstrap.Modal(document.getElementById('deleteTaskModal'));
    modal.show();
}

document.getElementById('confirmDelete').addEventListener('click', function() {
    if (taskToDelete) {
        fetch(`/task/${taskToDelete}/delete`, {
            method: 'POST'
        })
        .then(response => {
            if (response.redirected) {
                window.location.reload();
            }
        })
        .catch(error => console.error('Error:', error));
    }
});

// Filter tasks function
function filterTasks() {
    const searchInput = document.getElementById('taskSearchInput');
    const statusFilter = document.getElementById('statusFilter');
    const priorityFilter = document.getElementById('priorityFilter');
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');

    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const statusValue = statusFilter ? statusFilter.value : 'all';
    const priorityValue = priorityFilter ? priorityFilter.value : 'all';
    const categoryValue = categoryFilter ? categoryFilter.value : 'all';
    const sortValue = sortFilter ? sortFilter.value : 'due_date';
    const today = new Date();

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
            if (statusValue === 'overdue' && (!dueDate || new Date(dueDate) >= today || isCompleted)) visible = false;
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
    const priorityOrder = { "high": 0, "medium": 1, "low": 2 };
    if (taskList) {
        const visibleTasks = tasksArray.filter(card => card.style.display !== 'none');
        visibleTasks.sort((a, b) => {
            const aDueDate = a.getAttribute('data-due-date') || '';
            const bDueDate = b.getAttribute('data-due-date') || '';
            const aPriority = a.querySelector('.priority-badge').textContent.toLowerCase();
            const bPriority = b.querySelector('.priority-badge').textContent.toLowerCase();
            const aCreated = a.getAttribute('data-created') || '';
            const bCreated = b.getAttribute('data-created') || '';

            if (sortValue === 'due_date') {
                if (!aDueDate && !bDueDate) return 0;
                if (!aDueDate) return 1;
                if (!bDueDate) return -1;
                return new Date(aDueDate) - new Date(bDueDate);
            } else if (sortValue === 'priority') {
                return priorityOrder[aPriority] - priorityOrder[bPriority];
            } else if (sortValue === 'created') {
                return new Date(bCreated) - new Date(aCreated);
            } else {
                return 0;
            }
        });

        visibleTasks.forEach(task => taskList.appendChild(task));
    }
}

// Add event listeners
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('taskSearchInput');
    const statusFilter = document.getElementById('statusFilter');
    const priorityFilter = document.getElementById('priorityFilter');
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');

    if (searchInput) searchInput.addEventListener('input', filterTasks);
    if (statusFilter) statusFilter.addEventListener('change', filterTasks);
    if (priorityFilter) priorityFilter.addEventListener('change', filterTasks);
    if (categoryFilter) categoryFilter.addEventListener('change', filterTasks);
    if (sortFilter) sortFilter.addEventListener('change', filterTasks);
});

// Clear filters
document.getElementById('clearFilters').addEventListener('click', function() {
    document.getElementById('taskSearchInput').value = '';
    document.getElementById('statusFilter').value = 'all';
    document.getElementById('priorityFilter').value = 'all';
    document.getElementById('categoryFilter').value = 'all';
    document.getElementById('sortFilter').value = 'due_date';
    filterTasks();
});
