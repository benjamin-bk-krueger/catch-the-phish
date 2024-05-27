var act_width = 0;
var act_height = 0;
var act_top = 0;
var act_left = 0;

$(function(){
    $('img').each(function(){
        var img = new Image();
        img.onload = function() {
            // console.log($(this).attr('src') + ' - done!');
            var outerDiv = document.getElementsByClassName('master')[0];
            act_width = outerDiv.offsetWidth;
            act_height = outerDiv.offsetHeight;
            act_top = outerDiv.offsetTop;
            act_left = outerDiv.offsetLeft;

            var innerDiv = document.getElementsByClassName('area');
            for (var i = 0; i < innerDiv.length; i++)
            {
                innerDiv[i].style.setProperty('width', innerDiv[i].offsetWidth / (outerDiv.naturalWidth / outerDiv.offsetWidth) + 'px');
                innerDiv[i].style.setProperty('height', innerDiv[i].offsetHeight / (outerDiv.naturalHeight / outerDiv.offsetHeight) + 'px');
                innerDiv[i].style.setProperty('top', innerDiv[i].offsetTop / (outerDiv.naturalWidth / outerDiv.offsetWidth) + 'px');
                innerDiv[i].style.setProperty('left', innerDiv[i].offsetLeft / (outerDiv.naturalHeight / outerDiv.offsetHeight) + 'px');
            }

            const c1 = document.getElementById("c1");
            if (c1 != null) {
                c1.width = outerDiv.offsetWidth;
                c1.height = outerDiv.offsetHeight;
            }
        }
        img.src = $(this).attr('src');
    });
});

$(window).bind('resize', function(e){
    window.resizeEvt;
    $(window).resize(function(){
        clearTimeout(window.resizeEvt);
        window.resizeEvt = setTimeout(function(){
            var outerDiv = document.getElementsByClassName('master')[0];

            var innerDiv = document.getElementsByClassName('area');
            for (var i = 0; i < innerDiv.length; i++) {
                innerDiv[i].style.setProperty('width', innerDiv[i].offsetWidth / (act_width / outerDiv.offsetWidth) + 'px');
                innerDiv[i].style.setProperty('height', innerDiv[i].offsetHeight / (act_height / outerDiv.offsetHeight) + 'px');
                innerDiv[i].style.setProperty('top', innerDiv[i].offsetTop / (act_width / outerDiv.offsetWidth) + 'px');
                innerDiv[i].style.setProperty('left', innerDiv[i].offsetLeft / (act_height / outerDiv.offsetHeight) + 'px');
            }

            const c1 = document.getElementById("c1");
            if (c1 != null) {
                c1.width = outerDiv.offsetWidth;
                c1.height = outerDiv.offsetHeight;
            }

            act_width = outerDiv.offsetWidth;
            act_height = outerDiv.offsetHeight;
            act_top = outerDiv.offsetTop;
            act_left = outerDiv.offsetLeft;
        }, 250);
    });
});
