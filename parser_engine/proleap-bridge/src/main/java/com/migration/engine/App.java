package com.migration.engine;

import io.proleap.cobol.asg.metamodel.Program;
import io.proleap.cobol.asg.runner.impl.CobolParserRunnerImpl;
import io.proleap.cobol.preprocessor.CobolPreprocessor.CobolSourceFormatEnum;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

public class App {
    public static void main(String[] args) {
        try {
            // Check if Python gave us a file
            if (args.length == 0) {
                System.err.println("{\"error\": \"Please provide a COBOL file path.\"}");
                System.exit(1);
            }

            File cobolFile = new File(args[0]);
            
            // 1. Turn on the ProLeap Engine
            CobolParserRunnerImpl runner = new CobolParserRunnerImpl();
            
            // 2. Parse the file. We explicitly tell it to use standard FIXED COBOL format.
            Program program = runner.analyzeFile(cobolFile, CobolSourceFormatEnum.FIXED);
            
            // 3. Create a clean dictionary for our output
            Map<String, Object> astData = new HashMap<>();
            astData.put("file_name", cobolFile.getName());
            astData.put("status", "SUCCESS");
            
            if (program != null) {
                astData.put("is_parsed_by_proleap", true);
                // We removed the getName() line! Python will handle the extraction.
            }
            
            // 4. Convert to JSON and print for Python to capture
            ObjectMapper mapper = new ObjectMapper();
            System.out.println(mapper.writeValueAsString(astData));

        } catch (Exception e) {
            // Print error safely so Python doesn't crash
            System.err.println("{\"error\": \"" + e.toString() + "\"}");
        }
    }
}