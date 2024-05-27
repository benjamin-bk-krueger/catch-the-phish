var quiz_id;

function init_play(id) {
    quiz_id = "quiz-" + id;
}

$(function(){
    jsonval = JSON.parse("{}");
    Cookies.set(quiz_id, JSON.stringify(jsonval));
});

function clickanswer(answer) {
    val = Cookies.get(quiz_id);
    if (val) {
        jsonval = JSON.parse(val);
        jsonval[new String("answer")] = new Number(answer);
        Cookies.set(quiz_id, JSON.stringify(jsonval));
    } else {
        jsonval = JSON.parse("{}");
        jsonval[new String("answer")] = new Number(answer);
        Cookies.set(quiz_id, JSON.stringify(jsonval));
    }
}
