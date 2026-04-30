# ΑΣΕΠ Feed Dashboard — Οδηγός Εγκατάστασης

Αυτόματο dashboard για προκηρύξεις ΑΣΕΠ με εβδομαδιαία ανανέωση.
**Κόστος: $0** | **Χρόνος setup: ~15 λεπτά**

---

## 📁 Αρχεία

| Αρχείο | Περιγραφή |
|---|---|
| `index.html` | Το dashboard (hosted στο GitHub Pages) |
| `scraper.py` | Python scraper που μαζεύει τα δεδομένα |
| `data.json` | Τα δεδομένα (ενημερώνεται αυτόματα) |
| `.github/workflows/update.yml` | GitHub Actions — τρέχει τον scraper αυτόματα |

---

## 🚀 Βήματα Εγκατάστασης

### Βήμα 1 — Δημιούργησε GitHub λογαριασμό
Αν δεν έχεις: https://github.com/signup (δωρεάν)

### Βήμα 2 — Δημιούργησε νέο Repository
1. Πήγαινε στο https://github.com/new
2. Repository name: `asep-feed` (ή ό,τι θέλεις)
3. ✅ Public (απαραίτητο για GitHub Pages)
4. Κάνε κλικ **Create repository**

### Βήμα 3 — Ανέβασε τα αρχεία
1. Στο repository σου, κάνε κλικ **Add file → Upload files**
2. Ανέβασε: `index.html`, `scraper.py`, `data.json`
3. Για το workflow: δημιούργησε φάκελο `.github/workflows/` και ανέβασε το `update.yml`
   *(ή χρησιμοποίησε GitHub Desktop για πιο εύκολη διαχείριση)*

### Βήμα 4 — Ενεργοποίησε GitHub Pages
1. Settings → Pages (αριστερή στήλη)
2. Source: **Deploy from a branch**
3. Branch: **main** | Folder: **/ (root)**
4. Κάνε κλικ **Save**
5. Μετά από 1-2 λεπτά το site θα είναι στο:
   `https://USERNAME.github.io/asep-feed/`

### Βήμα 5 — Τρέξε τον scraper για πρώτη φορά
1. Πήγαινε στο repository → **Actions** tab
2. Κλικ στο **"Update ΑΣΕΠ Feed"**
3. Κλικ **"Run workflow"**
4. Περίμενε 1-2 λεπτά
5. Το `data.json` θα ενημερωθεί με πραγματικά δεδομένα!

---

## ⚙️ Αυτόματη Ανανέωση

Ο scraper τρέχει **κάθε Δευτέρα στις 07:00** αυτόματα.
Μπορείς να αλλάξεις τη συχνότητα στο αρχείο `update.yml`:

```yaml
# Κάθε μέρα στις 06:00
- cron: '0 3 * * *'

# Κάθε Δευτέρα και Πέμπτη
- cron: '0 4 * * 1,4'
```

---

## 📧 Email Ειδοποιήσεις (προαιρετικό)

Για να λαμβάνεις email όταν βγαίνουν νέες προκηρύξεις:
1. Πήγαινε στο [blogtrottr.com](https://blogtrottr.com)
2. Feed URL: `https://USERNAME.github.io/asep-feed/data.json`
3. Βάλε το email σου → Subscribe!

---

## 🔧 Troubleshooting

**Το site δεν φορτώνει δεδομένα:**
- Βεβαιώσου ότι το `data.json` υπάρχει στο root του repository
- Έλεγξε ότι το GitHub Pages είναι ενεργοποιημένο

**Ο scraper αποτυγχάνει:**
- Δες το log στο Actions tab
- Το asep.gr μπορεί να αλλάξει structure — άνοιξε issue στο repo

**Θέλω να προσθέσω νέα πηγή:**
- Πρόσθεσε νέα function στο `scraper.py`
- Κάλεσέ τη στο `main()`
