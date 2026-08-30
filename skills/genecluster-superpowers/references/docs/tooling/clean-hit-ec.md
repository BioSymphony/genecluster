# CLEAN and HIT-EC

**Status:** planned. Public source repositories exist, but this repository does not yet contain a public end-to-end fixture for a combined integration.

CLEAN and HIT-EC predict enzyme commission labels from protein sequence representations. Their predictions can complement similarity and domain evidence, but should remain a separate evidence channel with explicit confidence and abstention behavior.

## Public sources

- [CLEAN](https://github.com/tttianhao/CLEAN)
- [CLEAN-Contact](https://github.com/PNNL-CompBio/CLEAN-Contact)
- [HIT-EC](https://github.com/datax-lab/HIT-EC)

Use immutable releases or commits and follow each project's current model-weight and dependency instructions. Do not treat a mutable clone as a reproducible installation.

## Adoption requirements

Before changing the status from planned:

1. add a public or synthetic protein fixture;
2. record exact code and model versions;
3. verify licenses and model terms;
4. define a compact prediction and abstention schema;
5. compare the output with independent evidence;
6. document expected compute and cache size.

Private sequences, model credentials, and large caches must stay outside this repository.
