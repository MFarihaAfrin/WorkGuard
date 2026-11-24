import pandas as pd
from sklearn.linear_model import LogisticRegression
import joblib


data = {
    'amount_ratio': [
        0.10, 0.15, 0.90, 0.05, 0.98, 0.12, 0.50, 0.06, 0.94, 0.18, 0.04, 0.96,
        0.85, 0.20, 0.40, 0.92, 0.30, 0.60, 0.08, 0.99, 0.55, 0.25, 0.70, 0.35,
    ],
    'num_flags': [
        0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 2,
        3, 3, 2, 2, 2, 1, 2, 1, 0, 0, 1, 0,
    ],
    'risk': [
        0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 2,
        2, 2, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0,
    ],
}
df = pd.DataFrame(data)

X = df[['amount_ratio', 'num_flags']]
y = df['risk']

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, 'expenses/risk_model.pkl')
print("Model trained and saved.")


test_cases = [(0.10, 0), (0.90, 0), (0.10, 3), (0.90, 2), (0.50, 1)]
for amt, flags in test_cases:
    pred = model.predict([[amt, flags]])[0]
    print(f"amount_ratio={amt}, flags={flags} -> risk={pred}")