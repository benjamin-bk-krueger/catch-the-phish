var scenario_name;

function init_play(name) {
    scenario_name = name;
}

$(function(){
    jsonval = JSON.parse("{}");
    Cookies.set(scenario_name, JSON.stringify(jsonval));
});

function clickrating(level) {
    val = Cookies.get(scenario_name);
    if (val) {
        jsonval = JSON.parse(val);
        jsonval[new String("level")] = new Number(level);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    } else {
        jsonval = JSON.parse("{}");
        jsonval[new String("level")] = new Number(points);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    }
}

function clickmaster() {
    val = Cookies.get(scenario_name);
    if (val) {
        jsonval = JSON.parse(val);
        jsonval[new String("master")] = new Number(0);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    } else {
        jsonval = JSON.parse("{}");
        jsonval[new String("master")] = new Number(0);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    }
}

function clickarea(area_id, points) {
    var innerDiv = document.getElementsByClassName("area-" + area_id)[0];
    innerDiv.style.setProperty('opacity', '0.5');
    innerDiv.style.setProperty('background-color', 'yellow');

    val = Cookies.get(scenario_name);
    if (val) {
        jsonval = JSON.parse(val);
        jsonval[new String("area-" + area_id)] = new Number(points);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    } else {
        jsonval = JSON.parse("{}");
        jsonval[new String("area-" + area_id)] = new Number(points);
        Cookies.set(scenario_name, JSON.stringify(jsonval));
    }
}
