let dropArea = document.getElementById('upload_header')
;['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false)
})
function preventDefaults (e) {
    e.preventDefault()
    e.stopPropagation()
}
;['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, highlight, false)
})
;['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, unhighlight, false)
})

dropArea.addEventListener('drop',handleDrop,false)

function highlight(e) {
    dropArea.classList.add('highlight')
}
function unhighlight(e) {
    dropArea.classList.remove('highlight')
}
function handleDrop(e){
    uploadFiles(e.dataTransfer.files)
}
function uploadFiles(files) {
    let url = 'headerfile'
    let formData = new FormData()
    let filecount = 0
    ;[...files].forEach(file =>{
         formData.append('file'+String(filecount),file)
         filecount = filecount + 1
    })
    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.blob();
    })
    .then(blob => {
        return blob.text()
    })
    .then(text=> {
        let code_block = document.getElementById('code_area')
        code_block.innerHTML = text
    })
    .catch(() => { /* Error. Inform the user */ })
}
