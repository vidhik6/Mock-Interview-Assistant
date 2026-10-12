from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

pairs = [
    ('I built an API with caching and performance monitoring to reduce latency.', 'I built an API with caching and performance monitoring to reduce latency for users.'),
    ('This is good and good and good and good.', 'This project improved user trust and reduced support costs.'),
]
vec = TfidfVectorizer()
mat = cosine_similarity(vec.fit_transform([p[0] for p in pairs]), vec.transform([p[1] for p in pairs]))
print('TF-IDF demo scores:', mat.round(2).tolist())
