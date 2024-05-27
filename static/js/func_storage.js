var url_show_storage;
var csrf_token;

function init_storage(url, csrf) {
    url_show_storage = url;
    csrf_token = csrf;
}

/* Javascript magic: paste clipboard's image data by pressing ctrl-v and upload it to S3 storage */
document.onpaste = function(e){
    let items = e.clipboardData.items;
    let upload_progress = document.getElementById("upload_progress");
    if (e.clipboardData.items[0].kind === 'file') {
        upload_progress.style.width = "10%";
        upload_progress.ariaValueNow = "10";
        let imageFile = items[0].getAsFile();
        submitFileForm(imageFile, "paste");
    }
};

function ISODateString(d){
    function pad(n){return n<10 ? '0'+n : n}
    return d.getUTCFullYear()+'-'
        + pad(d.getUTCMonth()+1)+'-'
        + pad(d.getUTCDate())+'_'
        + pad(d.getUTCHours())+'-'
        + pad(d.getUTCMinutes())+'-'
        + pad(d.getUTCSeconds())
}

function sleep(duration) {
    return new Promise(resolve => {
        setTimeout(() => {
            resolve()
        }, duration * 1000)
    })
}

async function submitFileForm(file, type) {
    let upload_progress = document.getElementById("upload_progress");
    let date = new Date();
    let formData = new FormData();
    let myBlob = new Blob([file], {"type": "image/png"});
    formData.append('file', myBlob, 'upload_' + ISODateString(date)+ '.png');
    formData.append('csrf_token', csrf_token)
    formData.append('submission-type', type);
    formData.append('page_mode', 'upload');
    upload_progress.style.width = "20%";
    upload_progress.ariaValueNow = "20";

    let xhr = new XMLHttpRequest();
    xhr.open('POST', url_show_storage);
    xhr.onload = function () {
        if (xhr.status === 200) {
            console.log('all done: ');
        } else {
            console.log('Nope');
        }
    };

    xhr.send(formData);
    await sleep(1)
    upload_progress.style.width = "50%";
    upload_progress.ariaValueNow = "50";
    await sleep(5)
    upload_progress.style.width = "100%";
    upload_progress.ariaValueNow = "100";
    await sleep(1)
    window.location.assign(url_show_storage);
}

/*  More Javascript magic: enable list group filter and enable modal window error handling */
$(document).ready(function(){
    $("#myInput").on("keyup", function() {
        let value = $(this).val().toLowerCase();
        $("#myList li").filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1)
        });
    });
});

/* change the form fields - rename file */
function set_filename_field(filename) {
    document.forms['filename_change']['filename_new'].value = filename;
    document.forms['filename_change']['filename_old'].value = filename;
}
