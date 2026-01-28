const jsPsych = initJsPsych();

// Global variable to store current answer
var currentAnswer = null;

// Preload images
var preload = {
    type: jsPsychPreload,
    images: [
        'problem_1.png',
        'problem_2.png',
        'problem_3.png',
        'problem_4.png',
        'problem_5.png'
    ]
};

// Welcome & Consent
var welcome = {
    type: jsPsychHtmlButtonResponse,
    stimulus: '<h1>Program Comprehension Study</h1>' +
        '<div style="text-align: left; max-width: 800px; margin: 0 auto; line-height: 1.8;">' +
        '<p>Thank you for participating in this study.</p>' +
        '<p>In this experiment, you will be shown <strong>5 code snippets</strong> with input values. ' +
        'Your task is to <strong>calculate the return value</strong> of each function.</p>' +
        '<p><strong>Important:</strong></p>' +
        '<ul>' +
        '<li>You may use a calculator for arithmetic operations.</li>' +
        '<li>Take your time to understand the code before answering.</li>' +
        '<li>Your response time will be recorded.</li>' +
        '</ul>' +
        '<p>The study takes approximately <strong>15-20 minutes</strong>.</p>' +
        '<p>By clicking "I Agree", you consent to participate in this study.</p>' +
        '</div>',
    choices: ['I Agree']
};

// Participant Info (Name & Email)
var participantInfo = {
    type: jsPsychSurveyText,
    questions: [
        {
            prompt: 'Name',
            name: 'name',
            required: true,
            placeholder: 'Enter your name'
        },
        {
            prompt: 'Email',
            name: 'email',
            required: true,
            placeholder: 'Enter your email'
        }
    ]
};

// Demographics
var demographics = {
    type: jsPsychSurveyMultiChoice,
    questions: [
        {
            prompt: "How many years of programming experience do you have?",
            name: 'programming_exp',
            options: ['Less than 1 year', '1-2 years', '3-5 years', 'More than 5 years'],
            required: true
        },
        {
            prompt: "What is your experience level with Solidity or smart contracts?",
            name: 'solidity_exp',
            options: ['None', 'Beginner (read some code)', 'Intermediate (written some contracts)', 'Advanced (deployed contracts)'],
            required: true
        },
        {
            prompt: "What is your current role?",
            name: 'role',
            options: ['Undergraduate Student', 'Graduate Student', 'Software Developer', 'Researcher', 'Professor', 'Other'],
            required: true
        }
    ]
};

// Instructions
var instructions = {
    type: jsPsychHtmlButtonResponse,
    stimulus: '<h2>Instructions</h2>' +
        '<div style="text-align: left; max-width: 800px; margin: 0 auto; line-height: 1.8;">' +
        '<p>You will now see 5 problems. For each problem:</p>' +
        '<ol>' +
        '<li>Read the code carefully</li>' +
        '<li>Note the input values provided</li>' +
        '<li>Calculate the return value of the function</li>' +
        '<li>Enter your answer in the text box below the code</li>' +
        '<li>Click "Submit" when ready</li>' +
        '</ol>' +
        '<p><strong>Note:</strong> Enter only the numeric value (e.g., 1234), not variable names or expressions.</p>' +
        '<p>Click "Start" when you are ready.</p>' +
        '</div>',
    choices: ['Start']
};

// Problem data
var problems = [
    { image: 'problem_1.png', name: 'GreenHouse', complexity: 'Low', answer: 7651 },
    { image: 'problem_2.png', name: 'HubPool', complexity: 'Medium', answer: 954 },
    { image: 'problem_3.png', name: 'PercentageFeeModel', complexity: 'Medium-High', answer: 85 },
    { image: 'problem_4.png', name: 'LockupContract', complexity: 'High', answer: 6000 },
    { image: 'problem_5.png', name: 'Lock', complexity: 'High', answer: 6800 }
];

// Build timeline
var timeline = [preload, welcome, participantInfo, demographics, instructions];

// Create trials for each problem
for (var i = 0; i < problems.length; i++) {
    (function(index) {
        var problem = problems[index];

        var problem_trial = {
            type: jsPsychHtmlButtonResponse,
            stimulus: '<div style="display: flex; flex-direction: column; align-items: center;">' +
                '<div style="font-size: 18px; color: #666; margin-bottom: 15px;">Problem ' + (index + 1) + ' of 5</div>' +
                '<img src="' + problem.image + '" style="max-width: 900px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);">' +
                '<div style="margin-top: 25px; display: flex; align-items: center; gap: 15px;">' +
                '<label style="font-size: 18px;">Return value:</label>' +
                '<input type="number" id="answer-input-' + index + '" style="font-size: 22px; padding: 12px 20px; width: 180px; text-align: center; border: 2px solid #4CAF50; border-radius: 8px;" placeholder="Enter number">' +
                '</div>' +
                '</div>',
            choices: ['Submit'],
            data: {
                task: 'problem',
                problem_name: problem.name,
                problem_number: index + 1,
                complexity: problem.complexity,
                correct_answer: problem.answer
            },
            on_load: function() {
                var inputEl = document.getElementById('answer-input-' + index);
                if (inputEl) {
                    inputEl.focus();
                    inputEl.addEventListener('input', function() {
                        currentAnswer = this.value;
                    });
                    inputEl.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            currentAnswer = this.value;
                            document.querySelector('.jspsych-btn').click();
                        }
                    });
                }
            },
            on_finish: function(data) {
                var response = parseInt(currentAnswer);
                data.participant_answer = response;
                data.is_correct = (response === problem.answer);
                currentAnswer = null;
            }
        };
        timeline.push(problem_trial);

        // Break between problems
        if (index < problems.length - 1) {
            var break_trial = {
                type: jsPsychHtmlButtonResponse,
                stimulus: '<h3>Problem ' + (index + 1) + ' Complete</h3>' +
                    '<p>Take a short break if needed.</p>' +
                    '<p>Click "Next" when you are ready for the next problem.</p>',
                choices: ['Next']
            };
            timeline.push(break_trial);
        }
    })(i);
}

// Post Survey - Tools Used
var postSurvey = {
    type: jsPsychSurveyMultiChoice,
    questions: [
        {
            prompt: "Which tool or method did you primarily use to solve the problems?",
            name: 'tools_used',
            options: [
                'Mental calculation only (no tools)',
                'Calculator',
                'AI (e.g., ChatGPT, Claude, Copilot)',
                'Solidity IDE/Debugger (e.g., Remix, Hardhat)',
                'Pen and paper',
                'Other'
            ],
            required: true
        }
    ]
};
timeline.push(postSurvey);

// End
var end = {
    type: jsPsychHtmlButtonResponse,
    stimulus: '<h1>Thank You!</h1>' +
        '<p>Your responses have been recorded.</p>' +
        '<p>Thank you for participating in this study.</p>',
    choices: ['Finish']
};
timeline.push(end);

// Run the experiment
jsPsych.run(timeline);
