# API Choice

- **Étudiant** : Sabrina Mhidi
- **Date** : 19/05/2026

## API choisie : ipify

- **Endpoint principal** : `https://api.ipify.org?format=json`
- **Endpoint alternatif** : `https://api.ipify.org?format=text` (texte brut)
- **Documentation officielle** : https://www.ipify.org/
- **Authentification** : aucune (no auth)
- **Rate limit** : pas de limite officielle stricte, mais usage raisonnable recommandé

## Contrat de l'API

### Requête
- Méthode : `GET`
- Paramètres optionnels :
  - `format` : `json` | `text` | `jsonp` (défaut : `text`)
  - `callback` : nom de fonction (uniquement avec `format=jsonp`)

### Réponse attendue (format JSON)
- **Code HTTP** : `200 OK`
- **Header** : `Content-Type: application/json`
- **Body** :
```json
