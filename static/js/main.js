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
