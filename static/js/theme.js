// Toggle theme without reloading
function toggleTheme() {
    const body = document.body;
    body.classList.toggle("dark");

    document.cookie = "theme=" + (body.classList.contains("dark") ? "dark" : "light") + "; path=/";
}
