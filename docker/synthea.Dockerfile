# JRE-only image (Java Runtime Environment) — we don't need the full JDK
# here, since we're running an already-compiled .jar, not compiling anything.
FROM eclipse-temurin:17-jre-jammy

WORKDIR /synthea

# Download the pre-built Synthea release (official MITRE build) directly
# during the image build. curl is installed just for this and removed
# right after, so the final image doesn't carry unnecessary weight.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL -o synthea-with-dependencies.jar \
       https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["java", "-jar", "synthea-with-dependencies.jar"]