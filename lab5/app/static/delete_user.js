"use strict"

function fillModal(event) {
    let deleteUrl = event.relatedTarget.dataset.deleteUrl;

    let modalForm = event.target.querySelector("form");
    modalForm.action = deleteUrl;
}

window.onload = function () {
    let deleteModal = document.getElementById("delete-modal");
    deleteModal.addEventListener("show.bs.modal", fillModal);
}