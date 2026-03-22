# Introduction to Machine Learning
> Machine learning is a field of computer science that uses statistical techniques to give computer systems the ability to "learn" with data, without being explicitly programmed.

## The simplest way to think about it
Machine learning is all about learning from data. It involves using algorithms to identify patterns between input and output, and then using those patterns to make predictions or decisions. 
```
Traditional Programming
└── Explicit Code
└── Limited Flexibility
Machine Learning
└── Data-Driven
└── Adaptive
```

## What it is
### Definition
Machine learning is a field of computer science that uses statistical techniques to give computer systems the ability to "learn" with data, without being explicitly programmed. This means that instead of writing code for every possible scenario, you can use machine learning algorithms to identify patterns in data and make predictions or decisions.

### Key point
The key point to remember is that machine learning involves using data to train algorithms, rather than writing explicit code for every scenario.

### Example
For example, consider a spam email classifier. Instead of writing code to check for specific keywords, you can use machine learning to train an algorithm on a dataset of labeled emails (spam or not spam). The algorithm can then learn to recognize patterns in the data and make predictions on new, unseen emails.
| What it needs | How it works |
| --- | --- |
| Labeled dataset | Algorithm learns patterns |
| New, unseen data | Algorithm makes predictions |

## How it works
1. **Data collection**: Gather a dataset of labeled examples (e.g. spam or not spam emails).
2. **Algorithm selection**: Choose a suitable machine learning algorithm (e.g. logistic regression, decision tree).
3. **Training**: Train the algorithm on the dataset, allowing it to learn patterns and relationships.
```python
from sklearn import datasets
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

# Load dataset
iris = datasets.load_iris()
X = iris.data[:, :2]  # we only take the first two features.
y = iris.target

# Train/Test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
logreg = LogisticRegression()
logreg.fit(X_train, y_train)
```

## When to use / When to avoid
| Use this | Don't use this |
| --- | --- |
| Complex, data-driven problems | Simple, rule-based problems |
| Large datasets | Small datasets |

## Real-world examples
| Product/Use case | Why this fits |
| --- | --- |
| Spam email classifier | Machine learning can learn patterns in data to make predictions |
| Image recognition | Machine learning can recognize patterns in images to classify objects |

## The honest limitations / Gotchas
| Limitation | What to do |
| --- | --- |
| Overfitting | Regularization techniques, such as L1/L2 regularization |
| Bias-Variance Trade Off | Collect more data, use techniques such as cross-validation |

## TL;DR
- Machine learning is a field of computer science that uses statistical techniques to give computer systems the ability to "learn" with data.
- Machine learning involves using algorithms to identify patterns in data and make predictions or decisions.
- Machine learning is useful for complex, data-driven problems, but may not be suitable for simple, rule-based problems.

## You might also like
- [Machine Learning Life Cycle](#)
- [Project Development and Deployment](#)