$(function(){
    const c1 = document.getElementById("c1");
    const ctx1 = c1.getContext("2d");
    let origin = null;

    $canvas = $('#c1');

    const drawSelection = (e) => {
        ctx1.strokeStyle = "#000";
        ctx1.beginPath();
        ctx1.rect(origin.x, origin.y, e.offsetX - origin.x, e.offsetY - origin.y);
        ctx1.stroke();
    };

    const clear = () => {
        ctx1.strokeStyle = "#fff";
        ctx1.clearRect(0, 0, c1.width, c1.height);
    };

    const render = (e) => {
        clear();
        if (origin) drawSelection(e);
    }

    $canvas.mousedown(function(e) {
        e.preventDefault();
        var outerDiv = document.getElementsByClassName('master')[0];
        var ratioX = outerDiv.naturalWidth / outerDiv.offsetWidth;
        var ratioY = outerDiv.naturalHeight / outerDiv.offsetHeight;
        var imgX = Math.round(e.offsetX * ratioX);
        var imgY = Math.round(e.offsetY * ratioY);
        document.getElementById("start_x").value = imgX;
        document.getElementById("start_y").value = imgY;

        origin = {x: e.offsetX, y: e.offsetY};
    });

    $canvas.mouseup(function(e) {
        e.preventDefault();
        var outerDiv = document.getElementsByClassName('master')[0];
        var ratioX = outerDiv.naturalWidth / outerDiv.offsetWidth;
        var ratioY = outerDiv.naturalHeight / outerDiv.offsetHeight;
        var imgX = Math.round(e.offsetX * ratioX);
        var imgY = Math.round(e.offsetY * ratioY);
        if (imgX < document.getElementById("start_x").value) {
            document.getElementById("end_x").value =  document.getElementById("start_x").value;
            document.getElementById("start_x").value = imgX;
        } else {
            document.getElementById("end_x").value = imgX;
        }
        if (imgY < document.getElementById("start_y").value) {
            document.getElementById("end_y").value =  document.getElementById("start_y").value;
            document.getElementById("start_y").value = imgY;
        } else {
            document.getElementById("end_y").value = imgY;
        }

        document.getElementById("coords").innerHTML = document.getElementById("start_x").value + "," + document.getElementById("start_y").value + "-" + document.getElementById("end_x").value + "," + document.getElementById("end_y").value;

        origin = null;
        render(e);
    });

    $canvas.mousemove(function(e) {
        e.preventDefault();

        render(e);
    });
});
