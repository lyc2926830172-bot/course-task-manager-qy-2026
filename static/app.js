// 删除操作通过 POST 提交，先提示用户确认；核心功能不依赖 JavaScript。
document.querySelectorAll('form[data-confirm]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
