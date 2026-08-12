# Conflict table

Hard conflicts the model cannot reconcile. Audit catches duplicate semantics; this table catches impossible combinations.

## 视角冲突 (view conflict)

| A | B | why |
|---|---|---|
| `pov` | `full body` | cannot see own full body |
| `pov` | `cowboy shot` | mid/upper range needs more than POV sees |
| `from front` | `from behind` | physical opposite |
| `looking at viewer` | `facing away` | eye-line opposite |
| `from above` | `from below` | physical opposite |

## 身份冲突 (identity conflict)

| A | B | why |
|---|---|---|
| `solo` | `hetero`, `1boy`, `yuri` | single subject cannot interact |
| `completely nude` | any specific clothing | full nudity excludes clothing |
| `sleeping`, `unconscious` | `looking at viewer` | unconscious cannot look |
| `blindfold` | `heart-shaped pupils`, `rolling eyes` | eyes covered |

## 服装状态冲突 (clothing state conflict)

| A | B | why |
|---|---|---|
| `pantyhose` | `barefoot` | covered feet — except `torn pantyhose` |
| 套装内衣 (`cat lingerie`, `lace lingerie`, `babydoll`, `negligee`, `chemise`) | `no panties`, `bottomless` | set includes underwear |
| `partially undressed` | `completely nude` | exclusive states |

## 动作体位冲突 (action conflict)

| A | B | why |
|---|---|---|
| `standing sex` | `lying`, `on back` | body posture opposite |
| `missionary` | `doggystyle` | only one position at a time |
| `cowgirl position` | `prone bone` | position conflict |
| `fellatio` | `cunnilingus` (same actor) | one mouth, one action |

## 细节过度 (detail excess)

Each body part: ≤ 2 state tags, no mutual exclusion.

| Body part | Conflict pair |
|---|---|
| toes | `spread toes` + `toe scrunch`, `feet together` |
| fingers | `spread fingers` + `clenched fist`, `gripping` |
| breasts | `bouncing breasts` + `breasts squeeze together` |
| mouth | `open mouth` + `clenched teeth`, `closed mouth` |
| eyes | `rolling eyes` + `looking at viewer` |
| legs | `spread legs` + `legs together` |
