# Contribute

Overall guidance on contributing to a PyAnsys library appears in the
[Contributing] topic in the *PyAnsys developer's guide*. Ensure that you
are thoroughly familiar with this guide before attempting to contribute to
VISOR.

The following contribution information is specific to VISOR.

Additional information can be found in the
[VISOR Contributing](https://visor.docs.pyansys.com/version/dev/contributing/index.html)
documentation.

[Contributing]: https://dev.docs.pyansys.com/how-to/contributing.html

<!-- Begin content specific to your library here. -->

## SAF integration smoke test

The SAF smoke test uses an independently authored in-repository fixture and
public SAF dependencies, with no PIM or private POC requirement. See the
[fixture guide](tests/fixtures/saf_visor_solution/README.md) for coverage,
current-wheel build/setup commands, latest-stable SAF installation policy and diagnostics.

The SAF smoke test runs both geometry cases in every leg (Python 3.11-3.14) of the
`test` CI job, reusing its frontend and Dash builds, and the shared result check
gates its report. Normal smoke runs retain `-m "not saf"`. Explicitly selected SAF
tests fail rather than skip when prerequisites are unavailable.
