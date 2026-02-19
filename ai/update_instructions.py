#!/usr/bin/env python3
"""
Script to update system instructions in rag_query.py to include semantic_search_documents
"""

def main():
    file_path = '/Users/tamsar/Downloads/nabavkidata/ai/rag_query.py'

    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find and update the instructions section
    found_web_search = False
    for i, line in enumerate(lines):
        if '4. **web_search_procurement** - ПРЕБАРУВАЊЕ НА ЖИВО на e-nabavki.gov.mk и веб (РЕАЛНО ПРЕБАРУВА!)' in line:
            # Insert new semantic_search_documents entry before web_search_procurement
            new_text = """4. **semantic_search_documents** - 🤖 AI СЕМАНТИЧКО ПРЕБАРУВАЊЕ со вектори (pgvector + Gemini embeddings)
   Користи за: Концептуални пребарувања, комплексни спецификации, технички барања каде точните зборови не мора да се совпаѓаат
   МОЌНО: Пребарува по ЗНАЧЕЊЕ користејќи AI embeddings - не треба точно совпаѓање на зборови!
   Примери: "медицинска опрема за операции" → наоѓа: хируршки инструменти, стерилизатори, анестезија, дури и ако не се споменати точно тие зборови
   Идеално за: Технички спецификации, комплексни барања, концептуални пребарувања

5. **web_search_procurement** - ПРЕБАРУВАЊЕ НА ЖИВО на e-nabavki.gov.mk и веб (РЕАЛНО ПРЕБАРУВА!)
"""
            lines[i] = new_text
            found_web_search = True

            # Update numbering for subsequent tools
            if i+3 < len(lines) and '5. **get_tender_by_id**' in lines[i+3]:
                lines[i+3] = lines[i+3].replace('5. **get_tender_by_id**', '6. **get_tender_by_id**')
            if i+6 < len(lines) and '6. **analyze_competitors**' in lines[i+6]:
                lines[i+6] = lines[i+6].replace('6. **analyze_competitors**', '7. **analyze_competitors**')
            if i+10 < len(lines) and '7. **get_recommendations**' in lines[i+10]:
                lines[i+10] = lines[i+10].replace('7. **get_recommendations**', '8. **get_recommendations**')
            if i+14 < len(lines) and '8. **get_price_statistics**' in lines[i+14]:
                lines[i+14] = lines[i+14].replace('8. **get_price_statistics**', '9. **get_price_statistics**')
            break

    if not found_web_search:
        print("ERROR: Could not find web_search_procurement in instructions")
        return

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✓ Successfully updated system instructions in rag_query.py")
    print("✓ Added semantic_search_documents documentation")
    print("✓ Renumbered subsequent tools")

if __name__ == '__main__':
    main()
