# Provider Documentation: Search APIs

This document provides a detailed overview of three popular search APIs: Serper API, Google Custom Search Engine (CSE) JSON API, and Brave Search API. Each section includes information on endpoints, authentication, parameters, usage examples, response formats, rate limits, pricing, error handling, best practices, and limitations. A comparison table at the end summarizes key features of each provider.

## Providers

### Serper API

**Endpoints**

- Main: `https://google.serper.dev/search`[1]

**Authentication**

- API Key via header:  
  - `X-API-KEY: <Your API Key>`[1]
- Register at serper.dev for credentials[2]

**Parameters**  

- Required:
  - `q`: search query string  
- Optional:
  - `location` (country, city, etc.), language, other search customization[2][1]

**Request Example (Python)**

```python
import requests
import json

url = "https://google.serper.dev/search"
payload = json.dumps({"q": "apple inc"})
headers = {
    'X-API-KEY': 'API_KEY',
    'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)
print(response.text)
```

**Response Format**

- JSON containing organic results, answer boxes, knowledge graph, etc.[2]

**Rate Limits**

- Ultimate plan: 300 queries/sec, 15,000–18,000 searches/min, higher available by negotiation[1]
- Credit deducted per successful query; no queries once credits are exhausted[1]

**Pricing**

- Competitive, with free trial and tiered credits. Specifics vary by volume and package[3]

**Error Handling**

- Standard HTTP status codes and descriptive error messages for quota or parameter issues[1]

**Best Practices & Limitations**

- Real-time queries (no caching)
- Customize location/language for more relevant results
- Credits can run out, requiring careful tracking[1]
- Use environment variable `SERPER_API_KEY` for integration with frameworks[2]

***

### Google Custom Search Engine (CSE) JSON API

**Endpoints**

- Web Search: `https://www.googleapis.com/customsearch/v1` [REST, GET](4)[5]

**Authentication**

- API Key appended to request as `key` parameter  
- Requires Programmable Search Engine setup to get `cx` [Search Engine ID](4)

**Parameters**

- Required:
  - `key`: API key
  - `cx`: Search Engine ID
  - `q`: search query string
- Optional:
  - `safe`: safe search (active, off)
  - `num`: number of results per page (max 10)
  - `start`: index of first result
  - `lr`: language restrict
  - `gl`: country restrict
  - `searchType`: image/web
  - `fields`: response filtering
  - `sort`: results sorting, if configured[5][4]

**Usage Example**

```
GET https://www.googleapis.com/customsearch/v1?key=API_KEY&cx=SEARCH_ENGINE_ID&q=apple
```

**Response Format**

- JSON, containing metadata, search items, and navigation info[5][4]

**Rate Limits**

- 100 free queries/day per API key;
- $5/1000 queries; up to 10,000/day[6][5]

**Pricing**

- Free up to 100/day, $5/1,000 queries beyond; 10k daily maximum[6][5]

**Error Handling**

- JSON-formatted errors with code, message, details
- Common errors: quota exceeded, invalid parameters, API key issues[4]

**Best Practices & Limitations**

- Only queries against configured search engines (cannot search all of Google directly)
- Support for pagination via `nextPage`/`previousPage` in results
- Results are limited in freshness compared to direct Google Search[5][4]
- Monitor usage in Google Cloud Console[5]

***

### Brave Search API

**Endpoints**

- Web Search: `https://api.search.brave.com/res/v1/web/search`[7][8]

**Authentication**

- Requires subscription (including Free plan)
- API key submitted via header:  
  - `X-Subscription-Token: <YOUR_API_KEY>`[7]

**Parameters**

- Required:
  - `q`: search query string[7]
- Optional:
  - `limit`: number of results [default 10](9)
  - Others depend on subscription level and endpoint, e.g., preferences, safe search, language[9][7]

**Request Example (cURL)**

```
curl -s --compressed "https://api.search.brave.com/res/v1/web/search?q=brave+search" \
-H "Accept: application/json" \
-H "Accept-Encoding: gzip" \
-H "X-Subscription-Token: <YOUR_API_KEY>"
```

**Response Format**

- JSON: Array of organic results, title, URL, snippet. Rich results for news, images, videos, conversion, calculations, scores depending on subscription[10][7]

**Rate Limits**

- Tiered by subscription; specifics vary [usually starts with Free plan limits, paid plans scale higher](8)[7]
- Rate limits published in account dashboard after API key is acquired

**Pricing**

- Free and paid plans; free plan requires registration but is not charged[8][7]
- Paid plans scale by request volume, features[10]

**Error Handling**

- HTTP status codes, JSON error details [invalid API key, rate exceeded, malformed query, etc.](9)[7]

**Best Practices & Limitations**

- For commercial apps, use paid tiers for higher quota and additional endpoints
- Supports news, image, video, and rich knowledge results in certain plans[10]
- Avoid hitting rate limits: monitor usage and select plan appropriately
- Only HTTPS requests are supported[8][7]

***

### Comparison Table

| Feature           | Serper                   | Google CSE               | Brave Search             |
|-------------------|--------------------------|--------------------------|--------------------------|
| **Endpoint**      | `/search`                | `/customsearch/v1`       | `/res/v1/web/search`     |
| **Auth**          | API Key, Header          | API Key, URL Param       | API Key, Header          |
| **Params**        | `q` (+ loc/lang opts)    | `key`, `cx`, `q`, opts   | `q`, `limit`, opts       |
| **Response**      | JSON (Google-like)       | JSON (web/image)         | JSON (rich results)      |
| **Free Tier**     | Limited, trial           | 100/day                  | Free registration        |
| **Pricing**       | By credit/tier           | $5/1,000 queries         | Scaled, rich data plans  |
| **Rate Limit**    | Up to 300/sec (plan)     | 100/day (free)           | Plan-defined             |
| **Best Use**      | Fast, location-rich      | Custom site/web search   | Rich multi-modal search  |
| **Doc Resource**  | serper.dev, docs         | dev.google.com           | brave.com/search/api     | [1][4][7][9][5][8][10]

[1](https://rramos.github.io/2024/06/13/serper/)
[2](https://python.langchain.com/docs/integrations/providers/google_serper/)
[3](https://www.capturekit.dev/blog/4-best-scraper-serp-api)
[4](https://developers.google.com/custom-search/v1/introduction)
[5](https://developers.google.com/custom-search/v1/overview)
[6](https://blog.apify.com/top-google-serp-apis/)
[7](https://api-dashboard.search.brave.com/app/documentation)
[8](https://brave.com/search/api/)
[9](https://publicapi.dev/brave-search-api)
[10](https://brave.com/search/api/guides/what-sets-brave-search-api-apart/)
[11](https://serper.dev)
[12](https://www.scrapingdog.com/blog/best-serp-apis/)
[13](https://serpapi.com/blog/compare-serpapi-with-the-alternatives-serper-and-searchapi/)
[14](https://python.langchain.com/docs/integrations/tools/google_serper/)
[15](https://www.youtube.com/watch?v=D4tWHX2nCzQ)
[16](https://serpapi.com)
[17](https://programmablesearchengine.google.com/about/)
[18](https://brave.com/search/api/guides/)
[19](https://www.scraperapi.com/web-scraping/best-web-scraping-apis/google-serp-api/)
[20](https://cloud.google.com/generative-ai-app-builder/docs/migrate-from-cse)
