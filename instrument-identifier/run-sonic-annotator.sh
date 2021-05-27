#!/bin/bash


# Get audio file path
audio_path="$1"
if [ -z "${audio_path}" ]; then
    audio_path="audio"
fi

# Store standard input into audio file
mkdir -p "$(dirname -- "${audio_path}")"
cat > "${audio_path}"

# Call Sonic Annotator with arguments and file path
shift
arguments="$@"
echo Calling sonic-annotator ${arguments} "${audio_path}" 1>&2
sonic-annotator ${arguments} "${audio_path}"
error_code=$?

# Clean up audio file
rm "${audio_path}"

exit ${error_code}
