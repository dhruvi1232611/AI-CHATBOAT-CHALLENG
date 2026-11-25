"""Hybrid retriever: BM25 (lexical) + character n-gram cosine (fuzzy).
In production, swap the fuzzy half for dense embeddings stored in Qdrant."""
import math
import re
from collections import Counter

STOP = set("a an and are as at be by for from has have in is it of on or that the to was we will with our your their this these those can must should".split())


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#.]+", text.lower()) if w not in STOP and len(w) > 1]


def _ngrams(text: str, n: int = 3) -> Counter:
    s = " ".join(tokenize(text))
    return Counter(s[i:i + n] for i in range(max(len(s) - n + 1, 0)))


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class HybridRetriever:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75, alpha: float = 0.7):
        self.k1, self.b, self.alpha = k1, b, alpha
        self.tok = [tokenize(t) for t in texts]
        self.tf = [Counter(t) for t in self.tok]
        self.grams = [_ngrams(t) for t in texts]
        self.N = len(texts)
        self.avg = sum(len(t) for t in self.tok) / max(self.N, 1)
        self.df = Counter()
        for t in self.tok:
            self.df.update(set(t))

    def _bm25(self, query: str) -> list[float]:
        q, out = tokenize(query), []
        for i in range(self.N):
            score, dl = 0.0, len(self.tok[i])
            for term in q:
                f = self.tf[i].get(term, 0)
                if not f:
                    continue
                idf = math.log(1 + (self.N - self.df[term] + 0.5) / (self.df[term] + 0.5))
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
            out.append(score)
        return out

    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        lex = self._bm25(query)
        qg = _ngrams(query)
        fuzzy = [_cosine(qg, g) for g in self.grams]
        mx = max(lex) or 1.0
        mf = max(fuzzy) or 1.0
        scores = [self.alpha * (l / mx) + (1 - self.alpha) * (f / mf) for l, f in zip(lex, fuzzy)]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, round(s, 3)) for i, s in ranked[:k] if s > 0]
